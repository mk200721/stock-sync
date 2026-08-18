"""Inventory forecasting and optimization math.

Everything here is plain pandas/numpy so it can be unit-tested and reasoned
about without the UI. The two ideas a reviewer should take away:

  1. Demand forecasting — project the next N weeks from history.
  2. Inventory optimization — turn that forecast + lead time + demand
     variability into a safety stock, a reorder point, and an order quantity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Service-level z-scores for safety-stock sizing. Higher service level =>
# more buffer stock => fewer stockouts but more capital tied up.
SERVICE_LEVELS = {
    "90%": 1.2816,
    "95%": 1.6449,
    "97%": 1.8808,
    "99%": 2.3263,
}
DEFAULT_SERVICE_LEVEL = "95%"


# --------------------------------------------------------------------------
# Demand forecasting
# --------------------------------------------------------------------------
def moving_average_forecast(history: list[float], periods: int = 4, window: int = 4) -> list[float]:
    """Flat forecast = average of the last `window` observations."""
    hist = [float(x) for x in history if x is not None]
    if not hist:
        return [0.0] * periods
    window = min(window, len(hist))
    level = float(np.mean(hist[-window:]))
    return [round(level, 1)] * periods


def exp_smoothing_forecast(history: list[float], periods: int = 4, alpha: float = 0.4) -> list[float]:
    """Simple exponential smoothing — recent weeks weighted more heavily."""
    hist = [float(x) for x in history if x is not None]
    if not hist:
        return [0.0] * periods
    level = hist[0]
    for x in hist[1:]:
        level = alpha * x + (1 - alpha) * level
    return [round(level, 1)] * periods


def seasonal_naive_forecast(history: list[float], periods: int = 4, season: int = 4) -> list[float]:
    """Repeat the most recent `season`-length cycle forward."""
    hist = [float(x) for x in history if x is not None]
    if not hist:
        return [0.0] * periods
    tail = hist[-season:] if len(hist) >= season else hist
    return [round(tail[i % len(tail)], 1) for i in range(periods)]


FORECAST_METHODS = {
    "Exponential smoothing": exp_smoothing_forecast,
    "Moving average": moving_average_forecast,
    "Seasonal naive": seasonal_naive_forecast,
}


# --------------------------------------------------------------------------
# Inventory optimization
# --------------------------------------------------------------------------
def safety_stock(demand_std: float, lead_time_weeks: float, z: float) -> float:
    """Buffer against demand variability over the replenishment lead time."""
    return z * demand_std * math.sqrt(max(lead_time_weeks, 0.0))


def reorder_point(avg_demand: float, lead_time_weeks: float, ss: float) -> float:
    """Stock level that should trigger a new order."""
    return avg_demand * lead_time_weeks + ss


def weeks_until_stockout(current_stock: float, avg_demand: float) -> float:
    if avg_demand <= 0:
        return math.inf
    return current_stock / avg_demand


def stock_status(current_stock: float, rop: float) -> str:
    if current_stock <= 0:
        return "out"
    if current_stock <= rop * 0.5:
        return "critical"
    if current_stock <= rop:
        return "low"
    return "healthy"


STATUS_ORDER = {"out": 0, "critical": 1, "low": 2, "healthy": 3}
STATUS_LABEL = {"out": "OUT OF STOCK", "critical": "CRITICAL", "low": "LOW", "healthy": "OK"}


@dataclass
class Settings:
    service_level: str = DEFAULT_SERVICE_LEVEL
    forecast_method: str = "Exponential smoothing"
    forecast_weeks: int = 4

    @property
    def z(self) -> float:
        return SERVICE_LEVELS.get(self.service_level, SERVICE_LEVELS[DEFAULT_SERVICE_LEVEL])


def analyze(products: pd.DataFrame, demand: pd.DataFrame, settings: Settings | None = None) -> pd.DataFrame:
    """Enrich each product with demand stats, a forecast, and reorder advice.

    Parameters
    ----------
    products : columns product_id, name, category, unit_cost, current_stock,
               max_stock, lead_time_days
    demand   : long format, columns product_id, week, demand, (optional) fulfilled
    """
    settings = settings or Settings()
    forecaster = FORECAST_METHODS[settings.forecast_method]
    rows = []

    grouped = {pid: g for pid, g in demand.groupby("product_id")} if not demand.empty else {}

    for _, p in products.iterrows():
        pid = p["product_id"]
        g = grouped.get(pid)
        if g is not None and not g.empty:
            g = g.sort_values("week")
            hist = g["demand"].fillna(0).astype(float).tolist()
            fulfilled = g["fulfilled"].fillna(0).astype(float).tolist() if "fulfilled" in g else None
        else:
            hist, fulfilled = [], None

        avg_demand = float(np.mean(hist)) if hist else 0.0
        demand_std = float(np.std(hist, ddof=1)) if len(hist) > 1 else 0.0
        forecast = forecaster(hist, periods=settings.forecast_weeks) if hist else [0.0] * settings.forecast_weeks

        lead_weeks = float(p["lead_time_days"]) / 7.0
        ss = safety_stock(demand_std, lead_weeks, settings.z)
        rop = reorder_point(avg_demand, lead_weeks, ss)
        current = float(p["current_stock"])
        max_stock = float(p["max_stock"])
        status = stock_status(current, rop)

        # Order-up-to policy: when at/below the reorder point, refill to max.
        suggested_order = int(math.ceil(max(0.0, max_stock - current))) if current <= rop else 0

        if fulfilled is not None and sum(hist) > 0:
            fill_rate = min(100.0, sum(fulfilled) / sum(hist) * 100.0)
        else:
            fill_rate = 100.0

        rows.append({
            **p.to_dict(),
            "history": hist,
            "avg_demand": round(avg_demand, 1),
            "demand_std": round(demand_std, 2),
            "forecast": forecast,
            "forecast_total": round(sum(forecast), 1),
            "safety_stock": round(ss, 1),
            "reorder_point": round(rop, 1),
            "weeks_to_stockout": round(weeks_until_stockout(current, avg_demand), 1),
            "fulfillment_rate": round(fill_rate, 1),
            "status": status,
            "status_label": STATUS_LABEL[status],
            "status_rank": STATUS_ORDER[status],
            "suggested_order": suggested_order,
            "inventory_value": round(current * float(p["unit_cost"]), 2),
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["status_rank", "name"]).reset_index(drop=True)
    return result


def backtest(demand: pd.DataFrame, settings: Settings | None = None, holdout: int = 4) -> dict:
    """Measure forecast accuracy by hiding the last `holdout` weeks and predicting them.

    Returns model MAE/MAPE alongside a naive baseline (last-value carried forward),
    so the model's lift over "just repeat last week" is visible. This is the
    difference between "I forecasted" and "I forecasted, and here's how accurate."
    """
    settings = settings or Settings()
    forecaster = FORECAST_METHODS[settings.forecast_method]
    abs_err, ape, naive_err = [], [], []
    products_scored = 0

    if demand.empty:
        return {"mae": None, "mape": None, "naive_mae": None, "points": 0,
                "products": 0, "holdout": holdout, "method": settings.forecast_method}

    for _, g in demand.groupby("product_id"):
        hist = g.sort_values("week")["demand"].fillna(0).astype(float).tolist()
        if len(hist) <= holdout + 2:  # need enough history to train on
            continue
        train, test = hist[:-holdout], hist[-holdout:]
        preds = forecaster(train, periods=holdout)
        naive = train[-1]
        products_scored += 1
        for actual, pred in zip(test, preds):
            abs_err.append(abs(actual - pred))
            naive_err.append(abs(actual - naive))
            if actual > 0:
                ape.append(abs(actual - pred) / actual)

    if not abs_err:
        return {"mae": None, "mape": None, "naive_mae": None, "points": 0,
                "products": 0, "holdout": holdout, "method": settings.forecast_method}

    return {
        "mae": round(float(np.mean(abs_err)), 2),
        "mape": round(float(np.mean(ape)) * 100, 1) if ape else None,
        "naive_mae": round(float(np.mean(naive_err)), 2),
        "points": len(abs_err),
        "products": products_scored,
        "holdout": holdout,
        "method": settings.forecast_method,
    }
