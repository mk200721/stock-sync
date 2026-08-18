"""Load a real retail transaction log into Stock Sync's schema.

Source: the Kaggle "Retail Store Sales (dirty)" dataset, 12.5K transactions.
This module does the analyst work end to end:

  1. CLEAN  — impute missing Price/Quantity/Total via the identity
              Price x Quantity = Total Spent; drop rows with no item code
              (those are missing-completely-at-random, ~9.6%).
  2. RESHAPE — aggregate transactions into weekly demand per item over the
               most recent 52 weeks (a complete grid, zero-filled).
  3. BUILD  — a products table. The dataset has no inventory column, so
              on-hand stock is *simulated* from each item's own demand and
              clearly labelled as an assumption (see STOCK_ASSUMPTION).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

WEEKS = 52  # recent window used for the dashboard

# Lead times differ by how the goods are replenished — fresh stock comes
# frequently, furniture/electronics are slow. A defensible assumption, stated.
CATEGORY_LEAD_DAYS = {
    "Patisserie": 5, "Food": 6, "Milk Products": 5, "Butchers": 6, "Beverages": 7,
    "Furniture": 28, "Computers and electric accessories": 24,
    "Electric household essentials": 21,
}
DEFAULT_LEAD_DAYS = 10

STOCK_ASSUMPTION = (
    "This dataset records sales, not inventory. Current on-hand stock is simulated "
    "from each item's own average weekly demand (a deterministic spread of 0–10 "
    "weeks of cover) so the reorder logic has something to act on. Everything else "
    "— demand, forecasts, accuracy — comes straight from the real data."
)

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "retail_store_sales_dirty.csv"

_P, _Q, _T = "Price Per Unit", "Quantity", "Total Spent"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Impute the price/quantity/total triangle, drop codeless rows."""
    df = df.copy()
    # Recover each missing field from the other two (the rule holds exactly).
    df[_Q] = df[_Q].fillna((df[_T] / df[_P]).round())
    df[_P] = df[_P].fillna((df[_T] / df[_Q]).round(2))
    df[_T] = df[_T].fillna(df[_P] * df[_Q])
    df = df.dropna(subset=["Item", _Q, _P]).copy()
    df = df[df[_Q] > 0]
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"], errors="coerce")
    return df.dropna(subset=["Transaction Date"])


def load_transactions(path: str | Path | None = None, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (products_df, demand_df) ready for forecasting.analyze."""
    raw = pd.read_csv(path or _DEFAULT_PATH)
    df = clean(raw)

    # Keep the most recent 52 weeks and index them 1..52.
    max_date = df["Transaction Date"].max()
    cutoff = max_date - pd.Timedelta(weeks=WEEKS)
    df = df[df["Transaction Date"] > cutoff].copy()
    df["week"] = ((df["Transaction Date"] - cutoff).dt.days // 7 + 1).clip(1, WEEKS)

    items = sorted(df["Item"].unique())
    item_id = {name: i + 1 for i, name in enumerate(items)}

    # ---- weekly demand, zero-filled to a complete item x week grid ----
    sold = df.groupby(["Item", "week"])[_Q].sum().reset_index()
    grid = pd.MultiIndex.from_product([items, range(1, WEEKS + 1)], names=["Item", "week"])
    sold = sold.set_index(["Item", "week"]).reindex(grid, fill_value=0).reset_index()
    sold["product_id"] = sold["Item"].map(item_id)
    demand = pd.DataFrame({
        "product_id": sold["product_id"],
        "week": sold["week"],
        "demand": sold[_Q].astype(float),
        # Sales are realized (fulfilled) demand; lost sales are unobservable here.
        "fulfilled": sold[_Q].astype(float),
    })

    # ---- per-item attributes ----
    avg_weekly = demand.groupby("product_id")["demand"].mean()
    cost = df.groupby("Item")[_P].median()
    cat = df.groupby("Item")["Category"].agg(lambda s: s.mode().iat[0])

    rng = np.random.default_rng(seed)
    # Weeks of cover currently on hand — a realistic spread spanning empty
    # shelves through overstock, so every insight (stockout risk, overstock,
    # dead stock) reflects something genuinely present in the inventory.
    cover_choices = np.array([0, 2, 4, 8, 14, 22, 34])
    cover_weights = np.array([0.05, 0.12, 0.18, 0.25, 0.20, 0.12, 0.08])

    rows = []
    for name in items:
        pid = item_id[name]
        avg = float(avg_weekly.get(pid, 0.0))
        if avg > 0:
            weeks_on_hand = float(rng.choice(cover_choices, p=cover_weights))
            current_stock = int(round(avg * weeks_on_hand))
        else:
            # No recent sales — a dead SKU. Some still hold leftover stock.
            current_stock = int(rng.integers(0, 6))
        category = str(cat.get(name, "General"))
        rows.append({
            "product_id": pid,
            "name": name,
            "category": category,
            "unit_cost": round(float(cost.get(name, 0.0)), 2),
            "current_stock": current_stock,
            "max_stock": max(10, int(np.ceil(avg * 12))),
            "lead_time_days": CATEGORY_LEAD_DAYS.get(category, DEFAULT_LEAD_DAYS),
        })

    products = pd.DataFrame(rows)
    return products, demand
