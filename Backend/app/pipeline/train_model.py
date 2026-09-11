"""
Train a next-day demand forecasting model for established SKUs.

Split strategy: TIME-based, not random. Last 14 days of each SKU's history held
out as a test set -- this mimics the real deployment scenario (predict the
future using only the past) and avoids leaking future information into training,
which a random split would do.

Baseline: naive forecast = avg_sold_14d_lag1 (i.e. "assume tomorrow looks like
the last 14 days"). The ML model must beat this to justify its complexity.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import joblib

IN_PATH = "model_dataset.csv"
HOLDOUT_DAYS = 14

NUMERIC_FEATURES = [
    "avg_sold_7d_lag1", "avg_sold_14d_lag1", "avg_sold_28d_lag1",
    "std_sold_28d_lag1", "cv_sold_28d_lag1", "trend_ratio_lag1",
    "stockout_rate_28d_lag1", "day_of_week", "lead_time_days",
]
CATEGORICAL_FEATURES = ["category"]


def load_model_dataset(path=IN_PATH):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["sku_id", "date"]).reset_index(drop=True)


def time_based_split(df, holdout_days=HOLDOUT_DAYS):
    """Per SKU, last `holdout_days` rows go to test, everything before to train."""
    cutoff_per_sku = df.groupby("sku_id")["date"].transform(
        lambda d: d.max() - pd.Timedelta(days=holdout_days)
    )
    train = df[df["date"] <= cutoff_per_sku].copy()
    test = df[df["date"] > cutoff_per_sku].copy()
    return train, test


def build_design_matrix(df, category_columns=None):
    """One-hot encode category, keep numeric features as-is.
    category_columns passed in for test set so it matches train's columns exactly."""
    X = pd.get_dummies(df[CATEGORICAL_FEATURES], columns=CATEGORICAL_FEATURES)
    X = pd.concat([df[NUMERIC_FEATURES].reset_index(drop=True), X.reset_index(drop=True)], axis=1)
    if category_columns is not None:
        X = X.reindex(columns=category_columns, fill_value=0)
    return X


def mean_absolute_percentage_error(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mask = y_true != 0
    return (np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])).mean() * 100


if __name__ == "__main__":
    df = load_model_dataset()
    train, test = time_based_split(df)
    print(f"Train rows: {len(train)}  ({train['date'].min().date()} to {train['date'].max().date()})")
    print(f"Test rows:  {len(test)}  ({test['date'].min().date()} to {test['date'].max().date()})")
    print(f"Train SKUs: {train['sku_id'].nunique()}  Test SKUs: {test['sku_id'].nunique()}")

    X_train = build_design_matrix(train)
    y_train = train["units_sold"]
    X_test = build_design_matrix(test, category_columns=X_train.columns)
    y_test = test["units_sold"]

    # --- Baseline: naive forecast ---
    baseline_pred = test["avg_sold_14d_lag1"]
    baseline_mae = mean_absolute_error(y_test, baseline_pred)
    baseline_mape = mean_absolute_percentage_error(y_test, baseline_pred)

    # --- Model: Random Forest ---
    model = RandomForestRegressor(
        n_estimators=300, max_depth=8, min_samples_leaf=5,
        random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)
    model_pred = model.predict(X_test)
    model_mae = mean_absolute_error(y_test, model_pred)
    model_mape = mean_absolute_percentage_error(y_test, model_pred)

    print("\n=== Backtest results (last 14 days per SKU, held out) ===")
    print(f"{'Model':<20}{'MAE':>10}{'MAPE':>10}")
    print(f"{'Naive (14d avg)':<20}{baseline_mae:>10.2f}{baseline_mape:>9.1f}%")
    print(f"{'Random Forest':<20}{model_mae:>10.2f}{model_mape:>9.1f}%")
    improvement = (1 - model_mae / baseline_mae) * 100
    print(f"\nMAE improvement over naive baseline: {improvement:.1f}%")

    print("\n=== Feature importances ===")
    importances = pd.Series(model.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print(importances.round(3))

    # Save model + the exact column order it expects, needed for inference later
    joblib.dump(model, "demand_model.joblib")
    joblib.dump(list(X_train.columns), "demand_model_columns.joblib")
    print("\nSaved demand_model.joblib and demand_model_columns.joblib")
