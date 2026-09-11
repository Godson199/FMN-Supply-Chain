"""
Cleaning pipeline for project1_supply_chain_demand.csv
Run step by step, printing checks after each transformation.
"""
import pandas as pd
import numpy as np

RAW_PATH = "raw_data.csv"

def load_raw(path=RAW_PATH):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def normalize_category(df):
    """Collapse case-inconsistent category labels (e.g. 'Snacks' / 'SNACKS') to Title Case."""
    df = df.copy()
    df["category"] = df["category"].str.strip().str.title()
    return df


def drop_exact_duplicates(df):
    """Remove fully-duplicated (sku_id, date) rows. Verified all dupes are exact row copies,
    not conflicting records, so a straight drop_duplicates is safe here."""
    df = df.copy()
    before = len(df)
    df = df.drop_duplicates(subset=["sku_id", "date"], keep="first")
    after = len(df)
    print(f"Dropped {before - after} exact duplicate rows")
    return df


def fill_missing_units_sold(df):
    """units_sold nulls are isolated single-day gaps (verified: never consecutive,
    scattered across established SKUs, none on the 3 new SKUs). Linear interpolation
    per SKU is a defensible fill. Flag which rows were imputed for transparency."""
    df = df.copy()
    df = df.sort_values(["sku_id", "date"])
    df["units_sold_imputed"] = df["units_sold"].isna()
    df["units_sold"] = df.groupby("sku_id")["units_sold"].transform(
        lambda s: s.interpolate(method="linear").round()
    )
    # Edge case: a null at the very start/end of a SKU's series has no anchor on
    # one side for linear interpolation. Backfill/forward-fill within SKU as fallback.
    df["units_sold"] = df.groupby("sku_id")["units_sold"].transform(
        lambda s: s.bfill().ffill()
    )
    return df


def reconstruct_missing_closing_stock(df):
    """closing_stock nulls are isolated single-day gaps (verified: never consecutive,
    none on the 3 new SKUs). Reconstruct via the inventory identity:
        stock_t = stock_(t-1) - sold_t + received_t
    floored at 0 (stock cannot go negative -- floor represents a stockout/lost-sale day,
    which the identity check confirmed already happens elsewhere in the real data too).
    Walked forward per SKU so consecutive reconstructions (if any) chain correctly."""
    df = df.copy()
    df = df.sort_values(["sku_id", "date"]).reset_index(drop=True)
    df["closing_stock_imputed"] = df["closing_stock"].isna()

    for sku, idx in df.groupby("sku_id").groups.items():
        idx = list(idx)
        for i in idx:
            if pd.isna(df.loc[i, "closing_stock"]):
                pos = idx.index(i)
                if pos == 0:
                    # No prior day to reconstruct from -- leave for a fallback pass.
                    continue
                prev_i = idx[pos - 1]
                prev_stock = df.loc[prev_i, "closing_stock"]
                implied = prev_stock - df.loc[i, "units_sold"] + df.loc[i, "units_received"]
                df.loc[i, "closing_stock"] = max(implied, 0)
    return df


NEW_SKUS = ["SKU-2000", "SKU-2001", "SKU-2002"]


def fix_new_sku_lead_time(df):
    """For established SKUs, lead_time_days is a single fixed value (verified).
    For the 3 new SKUs, it changes almost daily across the same value set used
    elsewhere -- unset/placeholder data, not real values. Replace it with the
    category-level median lead time from established SKUs, and flag the rows
    so this assumption is visible downstream (README, UI, risk confidence)."""
    df = df.copy()
    df["lead_time_assumed"] = False

    established = df[~df["sku_id"].isin(NEW_SKUS)]
    cat_median_lead = (
        established.groupby(["category", "sku_id"])["lead_time_days"]
        .first()
        .groupby("category")
        .median()
    )

    for sku in NEW_SKUS:
        mask = df["sku_id"] == sku
        if not mask.any():
            continue
        cat = df.loc[mask, "category"].iloc[0]
        df.loc[mask, "lead_time_days"] = int(cat_median_lead[cat])
        df.loc[mask, "lead_time_assumed"] = True

    return df


def check_date_gaps(df):
    """For each SKU, compare actual row count to expected (first date -> last date, daily)."""
    report = []
    for sku, g in df.groupby("sku_id"):
        g = g.sort_values("date")
        expected_days = (g["date"].max() - g["date"].min()).days + 1
        actual_rows = len(g)
        report.append({
            "sku_id": sku,
            "first_date": g["date"].min(),
            "last_date": g["date"].max(),
            "expected_days": expected_days,
            "actual_rows": actual_rows,
            "missing_rows": expected_days - actual_rows,
        })
    return pd.DataFrame(report).sort_values("missing_rows", ascending=False)


if __name__ == "__main__":
    df = load_raw()
    print("BEFORE normalize_category, unique values:")
    print(sorted(df["category"].unique()))

    df = normalize_category(df)
    print("\nAFTER normalize_category, unique values:")
    print(sorted(df["category"].unique()))

    print("\nRow count unchanged:", len(df))

    print("\n--- Dropping exact duplicate rows ---")
    df = drop_exact_duplicates(df)
    print("Row count now:", len(df))

    print("\n--- Date gap check per SKU (after dedupe) ---")
    gaps = check_date_gaps(df)
    print(gaps.to_string(index=False))

    print("\n--- Filling missing units_sold ---")
    print("Nulls before:", df["units_sold"].isna().sum())
    df = fill_missing_units_sold(df)
    print("Nulls after:", df["units_sold"].isna().sum())
    print("Rows imputed:", df["units_sold_imputed"].sum())

    print("\n--- Reconstructing missing closing_stock ---")
    print("Nulls before:", df["closing_stock"].isna().sum())
    df = reconstruct_missing_closing_stock(df)
    print("Nulls after:", df["closing_stock"].isna().sum())
    print("Rows reconstructed:", df["closing_stock_imputed"].sum())

    print("\n--- Fixing unreliable lead_time_days on new SKUs ---")
    df = fix_new_sku_lead_time(df)
    for sku in NEW_SKUS:
        vals = df[df["sku_id"] == sku]["lead_time_days"].unique()
        print(f"{sku}: lead_time_days now constant at {vals}")

    OUT_PATH = "cleaned_data.csv"
    df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved cleaned dataset -> {OUT_PATH} ({len(df)} rows)")
