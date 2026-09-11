"""
Generate next-day demand forecasts and stock risk flags for every SKU.

Established SKUs (25): use the trained RandomForest model. The features it needs
are exactly the "current" (unlagged) rolling stats as of the LAST available date --
those become the lag1-equivalent inputs for predicting the day after.

New SKUs (3): can't be scored by the model (not enough history to build the lag
features it needs -- confirmed in build_model_dataset.py, they were dropped
entirely from the trainable dataset). Fallback: category-level average daily
demand from established SKUs' most recent 28 days, explicitly flagged as
low-confidence.

Risk logic (ratio-based, per the EDA finding that raw demand scale varies ~5x
across SKUs):
    projected_demand = predicted_next_day_demand * lead_time_days
    cover_ratio = current_stock / projected_demand
    STOCKOUT_RISK  if cover_ratio < 1.0   (will run out before a reorder arrives)
    OVERSTOCK      if cover_ratio > 2.0   (EDA: no established SKU currently
                                            exceeds ~2.44x, so 2.0 is a real,
                                            non-trivial threshold, not arbitrary)
    HEALTHY        otherwise
"""
import pandas as pd
import numpy as np
import joblib

FEATURES_PATH = "features.csv"
MODEL_PATH = "demand_model.joblib"
MODEL_COLUMNS_PATH = "demand_model_columns.joblib"
OUT_PATH = "risk_flags.csv"

NEW_SKUS = ["SKU-2000", "SKU-2001", "SKU-2002"]
OVERSTOCK_RATIO_THRESHOLD = 2.0

NUMERIC_FEATURES = [
    "avg_sold_7d", "avg_sold_14d", "avg_sold_28d", "std_sold_28d",
    "cv_sold_28d", "trend_ratio", "stockout_rate_28d", "day_of_week", "lead_time_days",
]
CATEGORICAL_FEATURES = ["category"]


def load_features(path=FEATURES_PATH):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["sku_id", "date"]).reset_index(drop=True)


def get_latest_snapshot(df):
    """Last available row per SKU -- these rolling stats become the model's
    inputs for forecasting the day right after the data ends."""
    latest = df.sort_values("date").groupby("sku_id").tail(1).copy()
    next_date = df["date"].max() + pd.Timedelta(days=1)
    latest["day_of_week"] = next_date.dayofweek
    return latest, next_date


def predict_established(latest_established, model, model_columns):
    """The 'current' (unlagged) rolling stats in features.csv, as of the last
    available date, are exactly what the model needs as inputs for forecasting
    the day after -- but they must be renamed to match the *_lag1 column names
    the model was trained on, or reindex() silently zero-fills every one of them."""
    df = latest_established.copy()
    rename_map = {c: f"{c}_lag1" for c in
                  ["avg_sold_7d", "avg_sold_14d", "avg_sold_28d", "std_sold_28d",
                   "cv_sold_28d", "trend_ratio", "stockout_rate_28d"]}
    df = df.rename(columns=rename_map)

    numeric_cols = list(rename_map.values()) + ["day_of_week", "lead_time_days"]
    X = pd.get_dummies(df[CATEGORICAL_FEATURES], columns=CATEGORICAL_FEATURES)
    X = pd.concat([df[numeric_cols].reset_index(drop=True), X.reset_index(drop=True)], axis=1)

    missing = set(model_columns) - set(X.columns)
    assert not missing, f"Column mismatch, would silently zero-fill: {missing}"

    X = X.reindex(columns=model_columns, fill_value=0)
    preds = model.predict(X)
    return preds


def predict_new_skus(latest_new, df_all):
    """Category-average daily demand from established SKUs' most recent 28 days,
    as a stand-in forecast. Explicitly lower confidence -- flagged in output."""
    established = df_all[~df_all["sku_id"].isin(NEW_SKUS)]
    recent_28d = established.sort_values("date").groupby("sku_id").tail(28)
    cat_avg = recent_28d.groupby("category")["units_sold"].mean()

    preds = latest_new["category"].map(cat_avg)
    return preds.values


def classify_risk(row):
    if row["projected_demand_leadtime"] == 0:
        return "HEALTHY"
    ratio = row["closing_stock"] / row["projected_demand_leadtime"]
    if ratio < 1.0:
        return "STOCKOUT_RISK"
    elif ratio > OVERSTOCK_RATIO_THRESHOLD:
        return "OVERSTOCK"
    return "HEALTHY"


if __name__ == "__main__":
    df = load_features()
    model = joblib.load(MODEL_PATH)
    model_columns = joblib.load(MODEL_COLUMNS_PATH)

    latest, next_date = get_latest_snapshot(df)
    print(f"Forecasting for: {next_date.date()}")

    is_new = latest["sku_id"].isin(NEW_SKUS)
    latest_established = latest[~is_new].copy()
    latest_new = latest[is_new].copy()

    latest_established["predicted_next_day_demand"] = predict_established(
        latest_established, model, model_columns
    )
    latest_established["confidence"] = "normal"

    latest_new["predicted_next_day_demand"] = predict_new_skus(latest_new, df)
    latest_new["confidence"] = "low (new SKU, category-average fallback)"

    result = pd.concat([latest_established, latest_new], ignore_index=True)
    result["projected_demand_leadtime"] = (
        result["predicted_next_day_demand"] * result["lead_time_days"]
    ).round(1)
    result["risk_flag"] = result.apply(classify_risk, axis=1)
    result["cover_ratio"] = (result["closing_stock"] / result["projected_demand_leadtime"]).round(2)

    out_cols = [
        "sku_id", "category", "closing_stock", "lead_time_days",
        "predicted_next_day_demand", "projected_demand_leadtime",
        "cover_ratio", "risk_flag", "confidence",
    ]
    result = result[out_cols].sort_values("cover_ratio")

    print("\n=== Risk flags, all SKUs ===")
    print(result.to_string(index=False))

    print("\n=== Risk summary ===")
    print(result["risk_flag"].value_counts())

    result.to_csv(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")
