from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DATA_PATH = PROJECT_ROOT / "project1_supply_chain_demand (1).csv"

app = FastAPI(title="Supply Chain Demand Watch API", version="1.0.0")


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["closing_stock"] = pd.to_numeric(df["closing_stock"], errors="coerce")
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce")
    df["lead_time_days"] = pd.to_numeric(df["lead_time_days"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def get_signals() -> pd.DataFrame:
    df = load_data(DATA_PATH)
    sku_summary = (
        df.groupby("sku_id", as_index=False)
        .agg(
            category=("category", "first"),
            lead_time_days=("lead_time_days", "max"),
            history_days=("date", lambda s: (s.max() - s.min()).days + 1),
            current_stock=("closing_stock", "last"),
            avg_daily_demand=("units_sold", "mean"),
        )
    )
    sku_summary["days_of_cover"] = sku_summary["current_stock"] / sku_summary["avg_daily_demand"].replace(0, pd.NA)
    sku_summary["expected_demand_lead_time"] = sku_summary["avg_daily_demand"] * sku_summary["lead_time_days"].fillna(0)

    conditions = [
        sku_summary["history_days"] < 30,
        sku_summary["current_stock"] < sku_summary["expected_demand_lead_time"],
        sku_summary["days_of_cover"] >= 45,
    ]
    choices = ["new", "stockout_risk", "overstock"]
    sku_summary["status"] = pd.Series(pd.NA, index=sku_summary.index, dtype="object")
    sku_summary["status"] = np.select(conditions, choices, default="healthy")
    sku_summary["status"] = sku_summary["status"].fillna("healthy")

    return sku_summary[[
        "sku_id",
        "category",
        "lead_time_days",
        "history_days",
        "current_stock",
        "avg_daily_demand",
        "days_of_cover",
        "expected_demand_lead_time",
        "status",
    ]].sort_values("status", kind="stable").reset_index(drop=True)


def build_summary(signals: pd.DataFrame) -> dict:
    status_counts = signals["status"].value_counts().to_dict()
    return {
        "total_skus": int(len(signals)),
        "status_counts": status_counts,
        "overstock_count": int(status_counts.get("overstock", 0)),
        "stockout_risk_count": int(status_counts.get("stockout_risk", 0)),
        "new_count": int(status_counts.get("new", 0)),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """
    <html>
      <head><title>Supply Chain Demand Watch</title></head>
      <body>
        <h1>Supply Chain Demand Watch</h1>
        <p>API is running.</p>
        <ul>
          <li><a href="/health">Health</a></li>
          <li><a href="/api/summary">Summary</a></li>
          <li><a href="/api/skus">SKUs</a></li>
        </ul>
      </body>
    </html>
    """


@app.get("/api/summary")
def summary() -> dict:
    return build_summary(get_signals())


@app.get("/api/skus")
def skus(status: str | None = Query(default=None), category: str | None = Query(default=None)) -> list[dict]:
    signals = get_signals()
    if status:
        signals = signals[signals["status"].str.casefold() == status.casefold()]
    if category:
        signals = signals[signals["category"].str.casefold() == category.casefold()]
    if status and signals.empty:
        raise HTTPException(status_code=404, detail=f"No SKUs found for status '{status}'.")
    return signals.to_dict(orient="records")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "data_file": DATA_PATH.name}