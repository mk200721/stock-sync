"""Flexible ingestion: turn whatever spreadsheet the user has into our schema.

The original tool demanded an exact sheet order and exact column headers, which
is why it only worked with a ChatGPT-built file. Here we instead:

  * accept .csv / .xlsx / .xls,
  * auto-*guess* which of the user's columns maps to each field, and
  * let the UI confirm/override the mapping before loading.
"""

from __future__ import annotations

import io
import re

import pandas as pd

# Field -> human label + synonyms we try to auto-detect in the user's headers.
PRODUCT_FIELDS: dict[str, dict] = {
    "product_id":      {"label": "Product ID", "required": False,
                        "syn": ["id", "sku", "productid", "itemid", "itemnumber", "code"]},
    "name":            {"label": "Product Name", "required": True,
                        "syn": ["name", "product", "productname", "item", "itemname", "description", "title"]},
    "category":        {"label": "Category", "required": False,
                        "syn": ["category", "type", "dept", "department", "group", "class"]},
    "unit_cost":       {"label": "Unit Cost", "required": False,
                        "syn": ["cost", "unitcost", "price", "unitprice", "costperunit", "wholesale"]},
    "current_stock":   {"label": "Current Stock", "required": True,
                        "syn": ["stock", "currentstock", "qty", "quantity", "onhand", "inventory", "instock", "available", "units"]},
    "max_stock":       {"label": "Max Stock", "required": False,
                        "syn": ["maxstock", "max", "capacity", "target", "maxinventory", "par", "parlevel"]},
    "lead_time_days":  {"label": "Lead Time (days)", "required": False,
                        "syn": ["leadtime", "lead", "leadtimedays", "leaddays", "replenishment"]},
}

# Sensible fallbacks when a non-required column is missing from the upload.
FIELD_DEFAULTS = {
    "category": "General",
    "unit_cost": 0.0,
    "max_stock": 200,
    "lead_time_days": 10,
}

_WEEK_RE = re.compile(r"^(week|wk|w)[\s_\-]*\d+$", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_file(uploaded) -> dict[str, pd.DataFrame]:
    """Read an uploaded file into {sheet_name: DataFrame}.

    `uploaded` is anything with a `.name` and readable bytes (e.g. a Streamlit
    UploadedFile). CSVs come back under the single key "data".
    """
    name = getattr(uploaded, "name", "data.csv")
    ext = name.rsplit(".", 1)[-1].lower()
    raw = uploaded.read() if hasattr(uploaded, "read") else uploaded

    if ext == "csv":
        return {"data": pd.read_csv(io.BytesIO(raw) if isinstance(raw, bytes) else raw)}

    sheets = pd.read_excel(io.BytesIO(raw) if isinstance(raw, bytes) else raw, sheet_name=None)
    return {name: df for name, df in sheets.items()}


def guess_mapping(columns: list[str]) -> dict[str, str | None]:
    """Best-effort field -> column guess based on header names."""
    normed = {col: _norm(col) for col in columns}
    mapping: dict[str, str | None] = {}
    for field, spec in PRODUCT_FIELDS.items():
        match = None
        for col, ncol in normed.items():
            if any(s == ncol for s in spec["syn"]):  # exact synonym first
                match = col
                break
        if match is None:
            for col, ncol in normed.items():
                if any(s in ncol or ncol in s for s in spec["syn"]):  # then substring
                    match = col
                    break
        mapping[field] = match
    return mapping


def detect_week_columns(columns: list[str]) -> list[str]:
    """Columns that look like weekly demand buckets (Week 1, Wk2, W_3...)."""
    return [c for c in columns if _WEEK_RE.match(str(c).strip())]


def build_products(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    """Apply a confirmed mapping to produce the canonical products table."""
    out = pd.DataFrame()
    n = len(df)
    for field, spec in PRODUCT_FIELDS.items():
        col = mapping.get(field)
        if col and col in df.columns:
            out[field] = df[col]
        elif field == "product_id":
            out[field] = range(1, n + 1)
        elif field == "name":
            out[field] = [f"Product {i}" for i in range(1, n + 1)]
        else:
            out[field] = FIELD_DEFAULTS.get(field)

    out["product_id"] = pd.to_numeric(out["product_id"], errors="coerce").fillna(
        pd.Series(range(1, n + 1))).astype(int)
    for num in ["unit_cost", "current_stock", "max_stock", "lead_time_days"]:
        out[num] = pd.to_numeric(out[num], errors="coerce").fillna(FIELD_DEFAULTS.get(num, 0))
    out["current_stock"] = out["current_stock"].astype(int)
    out["max_stock"] = out["max_stock"].clip(lower=1).astype(int)
    out["lead_time_days"] = out["lead_time_days"].clip(lower=1).astype(int)
    out["category"] = out["category"].fillna("General").astype(str)
    out["name"] = out["name"].fillna("Unnamed").astype(str)
    return out


def demand_from_wide(df: pd.DataFrame, id_field_col: str | None, week_cols: list[str]) -> pd.DataFrame:
    """Melt wide weekly-demand columns into long (product_id, week, demand)."""
    if not week_cols:
        return pd.DataFrame(columns=["product_id", "week", "demand", "fulfilled"])
    rows = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        pid = i
        if id_field_col and id_field_col in df.columns:
            try:
                pid = int(r[id_field_col])
            except (ValueError, TypeError):
                pid = i
        for w_idx, col in enumerate(week_cols, start=1):
            val = pd.to_numeric(r[col], errors="coerce")
            rows.append({"product_id": pid, "week": w_idx,
                         "demand": 0 if pd.isna(val) else float(val), "fulfilled": None})
    return pd.DataFrame(rows)


def demand_from_long(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize an already-long demand sheet (product_id, week, demand[, fulfilled])."""
    cols = {_norm(c): c for c in df.columns}
    pid = cols.get("productid") or cols.get("id") or cols.get("sku")
    week = cols.get("week") or cols.get("wk") or cols.get("period")
    dem = cols.get("demand") or cols.get("units") or cols.get("sales") or cols.get("qty")
    ful = cols.get("fulfilled") or cols.get("shipped") or cols.get("sold")
    if not (pid and week and dem):
        return pd.DataFrame(columns=["product_id", "week", "demand", "fulfilled"])
    out = pd.DataFrame({
        "product_id": pd.to_numeric(df[pid], errors="coerce"),
        "week": pd.to_numeric(df[week], errors="coerce"),
        "demand": pd.to_numeric(df[dem], errors="coerce").fillna(0.0),
        "fulfilled": pd.to_numeric(df[ful], errors="coerce") if ful else None,
    }).dropna(subset=["product_id", "week"])
    out["product_id"] = out["product_id"].astype(int)
    out["week"] = out["week"].astype(int)
    return out
