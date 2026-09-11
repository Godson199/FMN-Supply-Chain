"""
Build a leakage-free modeling dataset for demand forecasting.

Problem with using features.csv directly: avg_sold_7d/14d/28d etc. for day t are
computed using a rolling window that INCLUDES day t's own units_sold. Using those
to predict day t's units_sold would leak the answer into the features.

Fix: shift every rolling/derived feature by 1 day per SKU, so day t's features
only reflect information available at the START of day t (i.e. through day t-1).
Target stays as day t's actual units_sold.
"""
import pandas as pd
import numpy as np

IN_PATH = "features.csv"
OUT_PATH = "model_dataset.csv"

NEW_SKUS = ["SKU-2000", "SKU-2001", "SKU-2002"]

LAG_FEATURES = [
    "avg_sold_7d", "avg_sold_14d", "avg_sold_28d", "std_sold_28d",
    "cv_sold_28d", "trend_ratio", "stockout_rate_28d",
]


def load_features(path=IN_PATH):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["sku_id", "date"]).reset_index(drop=True)


def build_lagged_dataset(df):
    """Shift each rolling feature by 1 day per SKU. Add day-of-week (known in
    advance, not derived from sales) and keep lead_time_days/category as-is
    since those aren't leakage risks (known before the day's sales happen)."""
    df = df.copy()
    for col in LAG_FEATURES:
        df[f"{col}_lag1"] = df.groupby("sku_id")[col].shift(1)

    df["day_of_week"] = df["date"].dt.dayofweek  # 0=Monday
    return df


if __name__ == "__main__":
    df = load_features()
    df = build_lagged_dataset(df)

    model_cols = [f"{c}_lag1" for c in LAG_FEATURES] + [
        "day_of_week", "lead_time_days", "category", "sku_id", "date", "units_sold"
    ]
    model_df = df[model_cols].copy()

    print("Rows before dropping warmup NaNs:", len(model_df))
    before_na = model_df[[f"{c}_lag1" for c in LAG_FEATURES]].isna().sum()
    print("\nNaNs per lag feature (warmup period, expected):")
    print(before_na)

    model_df = model_df.dropna(subset=[f"{c}_lag1" for c in LAG_FEATURES])
    print("\nRows after dropping warmup NaNs:", len(model_df))
    print("New SKU rows remaining:", model_df["sku_id"].isin(NEW_SKUS).sum())

    model_df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved -> {OUT_PATH}")
