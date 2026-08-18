"""Auto-generated business insights — the "so what" layer.

A dashboard shows numbers. An analyst delivers the takeaway. This module reads
the analyzed inventory and writes plain-English findings a store owner (or a
hiring manager) can act on in one read: where cash is stuck, what's about to
stock out, what's dead weight, and how concentrated the catalog is.
"""

from __future__ import annotations

import math

import pandas as pd

# weeks-of-supply thresholds
OVERSTOCK_WEEKS = 12     # > a quarter of cover = capital sitting idle
DEAD_STOCK_WEEKS = 26    # > half a year of cover = barely moving


def _weeks_of_supply(stock: float, avg_demand: float) -> float:
    return stock / avg_demand if avg_demand > 0 else math.inf


def compute(adf: pd.DataFrame, accuracy: dict | None = None) -> list[dict]:
    """Return a ranked list of insight cards.

    Each card: {severity, icon, headline, detail, value}. `adf` is the output of
    forecasting.analyze; `accuracy` is the optional forecasting.backtest result.
    """
    if adf.empty:
        return []

    out: list[dict] = []
    n = len(adf)
    a = adf.copy()
    a["wos"] = [_weeks_of_supply(s, d) for s, d in zip(a["current_stock"], a["avg_demand"])]

    # --- capital tied up ---
    capital = a["inventory_value"].sum()
    out.append({
        "severity": "info", "icon": "💰", "value": f"${capital/1000:.1f}K",
        "headline": f"${capital/1000:.1f}K in working capital is tied up in inventory",
        "detail": f"across {n} SKUs at current cost.",
    })

    # --- reorder now ---
    reorder = a[a["suggested_order"] > 0]
    if not reorder.empty:
        units = int(reorder["suggested_order"].sum())
        out.append({
            "severity": "warn", "icon": "🛒", "value": str(len(reorder)),
            "headline": f"{len(reorder)} SKUs are at or below their reorder point",
            "detail": f"suggested replenishment totals {units:,} units. Order before they stock out.",
        })

    # --- stockout risk within lead time ---
    a["lead_weeks"] = a["lead_time_days"] / 7.0
    at_risk = a[a["weeks_to_stockout"] < a["lead_weeks"]]
    at_risk = at_risk[at_risk["current_stock"] > 0]
    if not at_risk.empty:
        names = ", ".join(at_risk.sort_values("weeks_to_stockout")["name"].head(3))
        out.append({
            "severity": "critical", "icon": "⏳", "value": str(len(at_risk)),
            "headline": f"{len(at_risk)} SKUs will run out before a new order can arrive",
            "detail": f"weeks-to-stockout is shorter than lead time. Most urgent: {names}.",
        })

    # --- overstock: cash idle in slow movers ---
    a["overstock_units"] = [
        max(0.0, s - d * OVERSTOCK_WEEKS) for s, d in zip(a["current_stock"], a["avg_demand"])
    ]
    a["overstock_value"] = a["overstock_units"] * a["unit_cost"]
    overstock = a[a["overstock_units"] > 0]
    if not overstock.empty:
        ov = overstock["overstock_value"].sum()
        out.append({
            "severity": "warn", "icon": "📦", "value": f"${ov/1000:.1f}K",
            "headline": f"${ov/1000:.1f}K is over-stocked — more than {OVERSTOCK_WEEKS} weeks of cover",
            "detail": f"{len(overstock)} SKUs hold inventory demand won't consume soon. Cash you could free up.",
        })

    # --- dead stock ---
    dead = a[(a["wos"] > DEAD_STOCK_WEEKS) & (a["current_stock"] > 0)]
    if not dead.empty:
        dv = dead["inventory_value"].sum()
        out.append({
            "severity": "warn", "icon": "🪦", "value": str(len(dead)),
            "headline": f"{len(dead)} SKUs are effectively dead stock",
            "detail": f"over {DEAD_STOCK_WEEKS} weeks of cover (~half a year). ${dv/1000:.1f}K parked here — stop reordering these.",
        })

    # --- catalog concentration (Pareto) ---
    a["total_demand"] = [sum(h) for h in a["history"]]
    if a["total_demand"].sum() > 0:
        ranked = a.sort_values("total_demand", ascending=False).reset_index(drop=True)
        cum = ranked["total_demand"].cumsum() / ranked["total_demand"].sum()
        items_for_80 = int((cum <= 0.8).sum()) + 1
        pct_items = items_for_80 / n * 100
        out.append({
            "severity": "info", "icon": "📊", "value": f"{pct_items:.0f}%",
            "headline": f"{items_for_80} of {n} SKUs ({pct_items:.0f}%) drive 80% of demand",
            "detail": "the long tail moves slowly — focus working capital and reorder attention on the head.",
        })

    # --- forecast accuracy ---
    if accuracy and accuracy.get("mae") is not None:
        mae, naive = accuracy["mae"], accuracy.get("naive_mae")
        lift = ""
        if naive and naive > 0:
            improvement = (naive - mae) / naive * 100
            lift = f" — {improvement:.0f}% better than a naive last-week guess" if improvement > 0 else ""
        mape = f", MAPE {accuracy['mape']}%" if accuracy.get("mape") is not None else ""
        out.append({
            "severity": "info", "icon": "🎯", "value": f"{mae}",
            "headline": f"Forecast accuracy: {mae} MAE{mape}{lift}",
            "detail": f"backtested on the last {accuracy['holdout']} weeks across {accuracy['products']} SKUs ({accuracy['method']}).",
        })

    order = {"critical": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda c: order.get(c["severity"], 3))
