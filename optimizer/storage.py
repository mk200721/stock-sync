"""Tiny local persistence so manual edits survive between visits.

For a single-user local app, two CSVs on disk is the right amount of machinery —
no database server to stand up. Swap this module for a real DB later without
touching the UI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_DIR = Path(__file__).resolve().parent.parent / ".data"
_PRODUCTS = _DIR / "products.csv"
_DEMAND = _DIR / "demand.csv"


def save(products: pd.DataFrame, demand: pd.DataFrame) -> None:
    _DIR.mkdir(exist_ok=True)
    products.to_csv(_PRODUCTS, index=False)
    demand.to_csv(_DEMAND, index=False)


def load() -> tuple[pd.DataFrame, pd.DataFrame] | None:
    if _PRODUCTS.exists() and _DEMAND.exists():
        return pd.read_csv(_PRODUCTS), pd.read_csv(_DEMAND)
    return None


def clear() -> None:
    for f in (_PRODUCTS, _DEMAND):
        f.unlink(missing_ok=True)
