"""
FastAPI backend for the Supply Chain Demand & Stock Risk app.

Endpoints:
  GET  /api/health
  GET  /api/risk-flags                 -> all SKUs, current risk flags
  GET  /api/sku/{sku_id}                -> single SKU's data
  GET  /api/sku/{sku_id}/explain        -> LLM explanation for one SKU
  POST /api/ask                         -> grounded Q&A over the risk data

Serves precomputed model output (data/risk_flags.csv, data/features.csv) --
these are refreshed by re-running the pipeline scripts (app/pipeline/) and
committing the new CSVs, not recomputed on every request.
"""
import os
import re
import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_NAME = "claude-sonnet-4-6"
NEW_SKUS = {"SKU-2000", "SKU-2001", "SKU-2002"}

app = FastAPI(title="Supply Chain Risk API")

# Allow the Vercel frontend (and local dev) to call this API.
# Tighten allow_origins to your exact Vercel URL once deployed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

_anthropic_client = None


def get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured on server")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


def load_risk_flags():
    path = DATA_DIR / "risk_flags.csv"
    if not path.exists():
        raise HTTPException(status_code=500, detail="risk_flags.csv not found -- run the pipeline first")
    return pd.read_csv(path)


def load_latest_features():
    path = DATA_DIR / "features.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").groupby("sku_id").tail(1).reset_index(drop=True)


def build_sku_payload(sku_id, risk_df, features_df):
    risk_row = risk_df[risk_df["sku_id"] == sku_id]
    if risk_row.empty:
        return None
    risk_row = risk_row.iloc[0]

    feat_row = features_df[features_df["sku_id"] == sku_id]
    trend_ratio = (
        float(feat_row["trend_ratio"].iloc[0])
        if not feat_row.empty and pd.notna(feat_row["trend_ratio"].iloc[0]) else None
    )
    stockout_rate = (
        float(feat_row["stockout_rate_28d"].iloc[0])
        if not feat_row.empty and pd.notna(feat_row["stockout_rate_28d"].iloc[0]) else None
    )

    return {
        "sku_id": sku_id,
        "category": risk_row["category"],
        "current_stock": float(risk_row["closing_stock"]),
        "lead_time_days": int(risk_row["lead_time_days"]),
        "predicted_next_day_demand": round(float(risk_row["predicted_next_day_demand"]), 1),
        "projected_demand_over_lead_time": float(risk_row["projected_demand_leadtime"]),
        "cover_ratio": float(risk_row["cover_ratio"]),
        "risk_flag": risk_row["risk_flag"],
        "forecast_confidence": risk_row["confidence"],
        "recent_demand_trend_ratio": round(trend_ratio, 2) if trend_ratio is not None else "not available",
        "stockout_frequency_pct": round(stockout_rate * 100, 1) if stockout_rate is not None else "not available",
        "stockout_frequency_note": "measured over its full history to date (may be less than 28 days for new SKUs)",
    }


EXPLANATION_SYSTEM_PROMPT = """You are a supply chain analyst assistant. You explain stock risk \
flags to business users in plain, direct English (2-4 sentences).

Rules:
- Use ONLY the numbers given to you in the payload. Never invent or assume any \
number, date, or fact not present in the payload.
- If forecast_confidence indicates low confidence, say so plainly and explain why \
(new SKU, limited history) -- don't present the forecast as equally reliable as \
an established SKU's.
- Be concrete: reference the actual numbers (stock level, cover ratio, lead time) \
rather than vague language.
- Do not recommend a specific reorder quantity unless the payload contains enough \
information to compute one exactly.
"""

QA_SYSTEM_PROMPT = """You are a supply chain analyst assistant answering questions \
about SKU stock risk. You will be given a JSON table of SKU risk data.

Rules:
- Answer ONLY using the data provided. Never invent SKU IDs, numbers, or facts \
not present in the data.
- If the data needed to answer isn't in the table, say so plainly rather than \
guessing.
- Be concise and direct.
- When listing SKUs, use their sku_id exactly as given.
"""


def extract_mentioned_sku(question, risk_df):
    known_suffixes = {sku.split("-")[1]: sku for sku in risk_df["sku_id"]}
    match = re.search(r"SKU[\s\-]?(\d{3,4})", question, re.IGNORECASE)
    if match:
        suffix = match.group(1).zfill(4)
        if suffix in known_suffixes:
            return known_suffixes[suffix]
    for bare_match in re.finditer(r"\b(\d{4})\b", question):
        if bare_match.group(1) in known_suffixes:
            return known_suffixes[bare_match.group(1)]
    return None


# ---------------------------------------------------------------- Schemas

class AskRequest(BaseModel):
    question: str


# ---------------------------------------------------------------- Routes

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/risk-flags")
def get_risk_flags():
    df = load_risk_flags()
    return df.to_dict(orient="records")


@app.get("/api/sku/{sku_id}")
def get_sku(sku_id: str):
    risk_df = load_risk_flags()
    features_df = load_latest_features()
    payload = build_sku_payload(sku_id, risk_df, features_df)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"{sku_id} not found")
    return payload


@app.get("/api/sku/{sku_id}/explain")
def explain_sku(sku_id: str):
    risk_df = load_risk_flags()
    features_df = load_latest_features()
    payload = build_sku_payload(sku_id, risk_df, features_df)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"{sku_id} not found")

    client = get_anthropic_client()
    user_prompt = f"Explain this SKU's risk flag to a supply chain manager:\n\n{json.dumps(payload, indent=2)}"
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=300,
        system=EXPLANATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return {"sku_id": sku_id, "explanation": response.content[0].text, "payload": payload}


@app.post("/api/ask")
def ask_question(request: AskRequest):
    risk_df = load_risk_flags()
    mentioned_sku = extract_mentioned_sku(request.question, risk_df)
    context_df = risk_df[risk_df["sku_id"] == mentioned_sku] if mentioned_sku else risk_df
    context_json = context_df.to_json(orient="records", indent=2)

    client = get_anthropic_client()
    user_prompt = f"Question: {request.question}\n\nSKU risk data:\n{context_json}"
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=400,
        system=QA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return {"question": request.question, "answer": response.content[0].text, "matched_sku": mentioned_sku}
