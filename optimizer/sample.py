"""Built-in demo data + the downloadable template.

This is what kills the cold-start problem: the app can populate itself with a
realistic dataset on first open, so nobody needs ChatGPT to hand-craft a file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (name, category, unit_cost, current_stock, max_stock, lead_time_days, base_weekly_demand)
_CATALOG = [
    ("Wireless Earbuds Pro",   "Electronics", 89.00, 12,  300, 14, 55),
    ("USB-C Charger 65W",      "Electronics", 24.50, 0,   400, 10, 70),
    ("4K Webcam",              "Electronics", 119.00, 145, 200, 21, 18),
    ("Mechanical Keyboard",    "Electronics", 74.00, 38,  250, 18, 32),
    ("Cotton Crew T-Shirt",    "Apparel",     8.50,  420, 1000, 7, 130),
    ("Running Shoes",          "Apparel",     52.00, 24,  300, 25, 40),
    ("Wool Beanie",            "Apparel",     11.00, 6,   200, 12, 28),
    ("Denim Jacket",           "Apparel",     46.00, 88,  150, 30, 15),
    ("Stainless Water Bottle", "Home",        16.00, 210, 500, 9,  60),
    ("Scented Candle Set",     "Home",        21.00, 4,   180, 14, 35),
    ("Bamboo Cutting Board",   "Home",        18.50, 132, 220, 20, 22),
    ("Ceramic Mug 12oz",       "Home",        9.00,  0,   600, 8,  95),
    ("Protein Powder 2lb",     "Grocery",     34.00, 58,  400, 11, 80),
    ("Organic Coffee Beans",   "Grocery",     14.50, 19,  500, 6,  110),
    ("Granola Bars (24pk)",    "Grocery",     12.00, 240, 450, 5,  140),
    ("Sparkling Water (12pk)", "Grocery",     6.50,  7,   800, 4,  160),
]

WEEKS = 12

# Canonical schema used everywhere downstream.
PRODUCT_COLUMNS = [
    "product_id", "name", "category", "unit_cost",
    "current_stock", "max_stock", "lead_time_days",
]


def demo_data(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (products_df, demand_df) for a realistic 16-SKU, 12-week store."""
    rng = np.random.default_rng(seed)
    products, demand_rows = [], []

    for i, (name, cat, cost, stock, mx, lead, base) in enumerate(_CATALOG, start=1):
        products.append({
            "product_id": i, "name": name, "category": cat, "unit_cost": cost,
            "current_stock": stock, "max_stock": mx, "lead_time_days": lead,
        })
        for w in range(1, WEEKS + 1):
            # Seasonality (a gentle sine wave) + Gaussian noise, floored at 0.
            seasonal = 1 + 0.25 * np.sin(2 * np.pi * w / WEEKS)
            noise = rng.normal(1.0, 0.18)
            d = max(0, round(base * seasonal * noise))
            fulfilled = min(d, max(0, round(d * rng.uniform(0.85, 1.0))))
            demand_rows.append({
                "product_id": i, "week": w,
                "demand": d, "fulfilled": fulfilled,
            })

    return pd.DataFrame(products), pd.DataFrame(demand_rows)


def template_products() -> pd.DataFrame:
    """A small, pre-filled example users can copy and edit."""
    return pd.DataFrame([
        {"product_id": 1, "name": "Example Widget A", "category": "Electronics",
         "unit_cost": 19.99, "current_stock": 40, "max_stock": 200, "lead_time_days": 10},
        {"product_id": 2, "name": "Example Widget B", "category": "Home",
         "unit_cost": 7.50, "current_stock": 8, "max_stock": 150, "lead_time_days": 14},
    ])


def template_demand() -> pd.DataFrame:
    """Matching demand template — one row per product per week."""
    rows = []
    for pid in (1, 2):
        for w in range(1, 5):
            rows.append({"product_id": pid, "week": w, "demand": 30 - w, "fulfilled": 28 - w})
    return pd.DataFrame(rows)


def template_excel_bytes() -> bytes:
    """The downloadable .xlsx template with both sheets."""
    import io

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        template_products().to_excel(xw, sheet_name="Products", index=False)
        template_demand().to_excel(xw, sheet_name="Weekly Demand", index=False)
    return buf.getvalue()


def empty_products() -> pd.DataFrame:
    return pd.DataFrame(columns=PRODUCT_COLUMNS)


def empty_demand() -> pd.DataFrame:
    return pd.DataFrame(columns=["product_id", "week", "demand", "fulfilled"])
