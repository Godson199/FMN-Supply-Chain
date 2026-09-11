"""
Feature engineering for project1_supply_chain_demand.
Reads cleaned_data.csv, derives per-SKU-per-day features needed for
demand forecasting and risk flagging.
"""
import pandas as pd
import numpy as np

IN_PATH = "cleaned_data.csv"
OUT_PATH = "features.csv"

NEW_SKUS = ["SKU-2000", "SKU-2001", "SKU-2002"]


def load_cleaned(path=IN_PATH):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["sku_id", "date"]).reset_index(drop=True)


def add_rolling_demand_features(df):
    """7/14/28-day rolling average and std of units_sold, per SKU.
    min_periods set low so short-history new SKUs still get a value from
    whatever days they have, instead of all-NaN."""
    df = df.copy()
    g = df.groupby("sku_id")["units_sold"]

    df["avg_sold_7d"] = g.transform(lambda s: s.rolling(7, min_periods=3).mean())
    df["avg_sold_14d"] = g.transform(lambda s: s.rolling(14, min_periods=5).mean())
    df["avg_sold_28d"] = g.transform(lambda s: s.rolling(28, min_periods=7).mean())
    df["std_sold_28d"] = g.transform(lambda s: s.rolling(28, min_periods=7).std())
    return df


def add_volatility_features(df):
    """Coefficient of variation (std/mean) over trailing 28 days -- normalizes
    volatility by demand scale so a high-volume SKU and a low-volume SKU are
    comparable (EDA showed ~5x scale spread across SKUs)."""
    df = df.copy()
    df["cv_sold_28d"] = (df["std_sold_28d"] / df["avg_sold_28d"]).replace([np.inf, -np.inf], np.nan)
    return df


def add_trend_feature(df):
    """Simple trend signal: recent (7d) average vs prior (14d) average.
    >1 means demand picking up, <1 means slowing down."""
    df = df.copy()
    g = df.groupby("sku_id")["units_sold"]
    prior_14d = g.transform(lambda s: s.shift(7).rolling(14, min_periods=5).mean())
    df["trend_ratio"] = (df["avg_sold_7d"] / prior_14d).replace([np.inf, -np.inf], np.nan)
    return df


def add_stockout_features(df):
    """Stockout flag per day, plus a trailing 28-day stockout frequency per SKU.
    EDA showed this is the strongest real-world risk signal in the data --
    new SKUs were stocked out 67-83% of their short history."""
    df = df.copy()
    df["is_stockout_day"] = (df["closing_stock"] == 0).astype(int)
    df["stockout_rate_28d"] = df.groupby("sku_id")["is_stockout_day"].transform(
        lambda s: s.rolling(28, min_periods=5).mean()
    )
    return df


def add_cover_features(df):
    """Days of cover = current stock / recent avg daily demand.
    cover_vs_leadtime = days of cover expressed as a multiple of the SKU's own
    lead time -- this is the ratio the EDA showed is the right basis for risk
    thresholds (below 1.0 = will run out before a reorder can arrive)."""
    df = df.copy()
    df["days_of_cover"] = df["closing_stock"] / df["avg_sold_14d"]
    df["days_of_cover"] = df["days_of_cover"].replace([np.inf, -np.inf], np.nan)
    df["cover_vs_leadtime"] = df["days_of_cover"] / df["lead_time_days"]
    return df


if __name__ == "__main__":
    df = load_cleaned()
    print("Loaded cleaned data:", df.shape)

    df = add_rolling_demand_features(df)
    df = add_volatility_features(df)
    df = add_trend_feature(df)
    df = add_stockout_features(df)
    df = add_cover_features(df)

    print("\nFull feature set, columns:")
    print(df.columns.tolist())

    print("\nSample row (established SKU, latest date):")
    sample = df[df["sku_id"] == "SKU-1019"].tail(1)
    print(sample.T)

    print("\nSample row (new SKU, latest date):")
    sample_new = df[df["sku_id"] == "SKU-2000"].tail(1)
    print(sample_new.T)

    df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved feature table -> {OUT_PATH} ({len(df)} rows)")
