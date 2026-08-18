"""Fetch the real datasets used in Stock Sync's demos.

The repo only ships ONE real dataset (a small Online Retail II sample, CC BY 4.0).
The others are larger or have unclear redistribution terms, so we don't commit
them — this script pulls them from the Hugging Face Hub into ./data on demand.

Usage:
    python scripts/fetch_datasets.py            # fetch all
    python scripts/fetch_datasets.py dataco     # fetch one by key
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PARQUET = "https://huggingface.co/datasets/{repo}/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"

# key -> (hub repo, output filename, license note)
SOURCES = {
    "online_retail": (
        "mariorivas17/online_retail", "online_retail_ii_full.csv",
        "Online Retail II (UCI) — real UK online retailer, CC BY 4.0",
    ),
    "dirty_retail": (
        "jason1966/ahmedmohamed2003_retail-store-sales-dirty-for-data-cleaning",
        "retail_store_sales_dirty.csv",
        "Retail Store Sales (dirty) — Kaggle mirror, license unspecified (research/demo use)",
    ),
    "dataco": (
        "alalfi/SupplyChainDataset", "dataco_supply_chain.csv",
        "DataCo Smart Supply Chain — real orders w/ lead times & profit",
    ),
}

GROCERY_SHARD = (
    "https://huggingface.co/api/datasets/dunnowho/grocery-sales-forecasting"
    "/parquet/default/train/0.parquet"
)


def fetch(key: str) -> None:
    repo, out, note = SOURCES[key]
    print(f"• {key}: {note}")
    df = pd.read_parquet(PARQUET.format(repo=repo))
    # Drop masked PII columns if present (DataCo).
    df = df.drop(columns=[c for c in ["Customer_Email", "Customer_Password",
                                      "Customer_Fname", "Customer_Lname",
                                      "Customer_Street"] if c in df.columns])
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(DATA_DIR / out, index=False)
    print(f"  -> data/{out}  ({len(df):,} rows)")


def fetch_grocery() -> None:
    print("• grocery: Corporación Favorita — 1 of 10 shards (~9M rows)")
    df = pd.read_parquet(GROCERY_SHARD)
    DATA_DIR.mkdir(exist_ok=True)
    df.to_parquet(DATA_DIR / "grocery_favorita_shard0.parquet", index=False)
    print(f"  -> data/grocery_favorita_shard0.parquet  ({len(df):,} rows)")


def main() -> None:
    keys = sys.argv[1:] or list(SOURCES) + ["grocery"]
    for key in keys:
        if key == "grocery":
            fetch_grocery()
        elif key in SOURCES:
            fetch(key)
        else:
            print(f"unknown dataset key: {key} (choose from {list(SOURCES) + ['grocery']})")


if __name__ == "__main__":
    main()
