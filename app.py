"""Stock Sync — inventory forecasting & reorder optimization.

A Streamlit rebuild of the original single-file HTML tool. The headline change:
the app is usable the instant you open it (demo data), accepts any spreadsheet
(column mapping), and lets you type data in by hand — no ChatGPT-shaped file
required.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pathlib import Path

from optimizer import forecasting, ingest, insights, retail, sample, storage
from optimizer.forecasting import FORECAST_METHODS, SERVICE_LEVELS, Settings

SEV_COLOR = {"critical": "#FF5252", "warn": "#FFD740", "info": "#00E5FF"}
RETAIL_CSV = Path(__file__).resolve().parent / "data" / "retail_store_sales_dirty.csv"

# --------------------------------------------------------------------------
# Palette + page setup
# --------------------------------------------------------------------------
ACCENT, GREEN, YELLOW, RED = "#00E5FF", "#00E676", "#FFD740", "#FF5252"
PURPLE, BLUE, DIM = "#B388FF", "#448AFF", "#7A8AA8"
SERIES = ["#00E5FF", "#00E676", "#B388FF", "#FFAB40", "#FFD740", "#FF5252",
          "#448AFF", "#FF80AB", "#69F0AE", "#EA80FC", "#80D8FF", "#FF8A80",
          "#82B1FF", "#CCFF90", "#FFE57F", "#B9F6CA"]
STATUS_COLOR = {"out": RED, "critical": RED, "low": YELLOW, "healthy": GREEN}

st.set_page_config(page_title="Stock Sync", page_icon="📦", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background: #06080F; }
      h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.3px; }
      [data-testid="stMetric"] {
          background: linear-gradient(135deg, #0D1321, #111B2E);
          border: 1px solid #1A2540; border-radius: 14px; padding: 14px 16px;
      }
      [data-testid="stMetricValue"] { font-size: 26px; }
      .badge { font-size: 10px; font-weight: 700; letter-spacing: 0.6px;
               padding: 3px 9px; border-radius: 6px; white-space: nowrap; }
      .prodcard { background: linear-gradient(135deg,#0D1321,#111B2E);
                  border: 1px solid #1A2540; border-radius: 14px; padding: 14px 16px;
                  margin-bottom: 12px; }
      .bar-track { height: 5px; background: #1A2540; border-radius: 3px; margin-top: 8px; overflow: hidden; }
      .bar-fill { height: 100%; border-radius: 3px; }
      .muted { color: #7A8AA8; font-size: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def style_fig(fig: go.Figure, height: int = 260) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=DIM, size=11, family="Space Grotesk"),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
    )
    fig.update_xaxes(gridcolor="rgba(26,37,64,0.5)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(26,37,64,0.5)", zeroline=False)
    return fig


def badge(status: str, label: str) -> str:
    c = STATUS_COLOR[status]
    return f'<span class="badge" style="background:{c}22;color:{c};border:1px solid {c}44">{label}</span>'


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def init_state() -> None:
    if "products" not in st.session_state:
        saved = storage.load()
        if saved is not None:
            st.session_state.products, st.session_state.demand = saved
            st.session_state.loaded = True
        else:
            st.session_state.products = sample.empty_products()
            st.session_state.demand = sample.empty_demand()
            st.session_state.loaded = False
    st.session_state.setdefault("pending", None)
    st.session_state.setdefault("settings", Settings())


def set_data(products: pd.DataFrame, demand: pd.DataFrame, persist: bool = True) -> None:
    st.session_state.products = products.reset_index(drop=True)
    st.session_state.demand = demand.reset_index(drop=True)
    st.session_state.loaded = len(products) > 0
    st.session_state.pending = None
    st.session_state.data_note = None  # cleared unless a loader sets one
    if persist:
        storage.save(st.session_state.products, st.session_state.demand)


init_state()


# --------------------------------------------------------------------------
# Sidebar — data source + settings
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📦 Stock Sync")
    st.caption("Inventory forecasting & reorder optimization")

    st.markdown("#### Data source")
    if st.button("🚀 Load demo data", use_container_width=True, type="primary"):
        set_data(*sample.demo_data())
        st.rerun()

    if RETAIL_CSV.exists():
        if st.button("🛒 Load real retail data", use_container_width=True,
                     help="12.5K real Kaggle transactions, cleaned and reshaped into 200 SKUs."):
            set_data(*retail.load_transactions())
            st.session_state.data_note = retail.STOCK_ASSUMPTION
            st.rerun()

    up = st.file_uploader("Upload CSV / Excel", type=["csv", "xlsx", "xls"], key="uploader")
    if up is not None and st.session_state.get("last_upload") != up.file_id:
        st.session_state.last_upload = up.file_id
        try:
            st.session_state.pending = {"sheets": ingest.load_file(up), "name": up.name}
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not read file: {e}")

    st.download_button(
        "⬇️ Download Excel template", data=sample.template_excel_bytes(),
        file_name="stock_sync_template.xlsx", use_container_width=True,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if st.session_state.loaded:
        st.divider()
        st.markdown("#### Forecast settings")
        s: Settings = st.session_state.settings
        s.forecast_method = st.selectbox("Method", list(FORECAST_METHODS), index=list(FORECAST_METHODS).index(s.forecast_method))
        s.service_level = st.selectbox("Service level", list(SERVICE_LEVELS), index=list(SERVICE_LEVELS).index(s.service_level))
        s.forecast_weeks = st.slider("Forecast horizon (weeks)", 2, 8, s.forecast_weeks)

        st.divider()
        csv = st.session_state.products.to_csv(index=False).encode()
        st.download_button("⬇️ Export products CSV", csv, "products.csv", use_container_width=True)
        if st.button("🗑️ Clear all data", use_container_width=True):
            storage.clear()
            for k in ("products", "demand", "loaded", "pending"):
                st.session_state.pop(k, None)
            st.rerun()


# --------------------------------------------------------------------------
# Column-mapping screen (shown after an upload, before loading)
# --------------------------------------------------------------------------
def mapping_screen(pending: dict) -> None:
    st.title("Map your columns")
    st.caption(f"From **{pending['name']}** — confirm which of your columns is which. We pre-filled our best guesses.")

    sheets = pending["sheets"]
    sheet_names = list(sheets)
    psheet = st.selectbox("Which sheet holds your products?", sheet_names, index=0)
    pdf = sheets[psheet]
    cols = list(pdf.columns)
    st.dataframe(pdf.head(5), use_container_width=True)

    guess = ingest.guess_mapping(cols)
    st.markdown("#### Product fields")
    mapping: dict[str, str | None] = {}
    grid = st.columns(2)
    for i, (field, spec) in enumerate(ingest.PRODUCT_FIELDS.items()):
        with grid[i % 2]:
            opts = ["— none —"] + cols
            default = opts.index(guess[field]) if guess[field] in cols else 0
            label = spec["label"] + (" *" if spec["required"] else "")
            choice = st.selectbox(label, opts, index=default, key=f"map_{field}")
            mapping[field] = None if choice == "— none —" else choice

    # ---- demand history ----
    st.markdown("#### Demand history")
    week_cols = ingest.detect_week_columns(cols)
    other_sheets = [s for s in sheet_names if s != psheet]
    demand_opts = []
    if week_cols:
        demand_opts.append("Weekly columns in this sheet")
    if other_sheets:
        demand_opts.append("A separate sheet")
    demand_opts.append("No demand history")
    dmode = st.radio("Where is weekly demand?", demand_opts, horizontal=True)

    demand_df = sample.empty_demand()
    if dmode == "Weekly columns in this sheet":
        chosen = st.multiselect("Week columns (in order)", cols, default=week_cols)
        demand_df = ingest.demand_from_wide(pdf, mapping.get("product_id"), chosen)
    elif dmode == "A separate sheet":
        dsheet = st.selectbox("Demand sheet", other_sheets)
        ddf = sheets[dsheet]
        long = ingest.demand_from_long(ddf)
        if long.empty:
            wk = ingest.detect_week_columns(list(ddf.columns))
            id_guess = ingest.guess_mapping(list(ddf.columns)).get("product_id")
            long = ingest.demand_from_wide(ddf, id_guess, wk)
        demand_df = long

    c1, c2 = st.columns([1, 4])
    if c1.button("✅ Load data", type="primary"):
        if not mapping.get("name") or not mapping.get("current_stock"):
            st.error("Please map at least **Product Name** and **Current Stock**.")
        else:
            products = ingest.build_products(pdf, mapping)
            set_data(products, demand_df)
            st.rerun()
    if c2.button("Cancel"):
        st.session_state.pending = None
        st.rerun()


# --------------------------------------------------------------------------
# Welcome screen (nothing loaded yet)
# --------------------------------------------------------------------------
def welcome_screen() -> None:
    st.title("📦 Stock Sync")
    st.markdown("##### Forecast demand, size safety stock, and know exactly when to reorder.")
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1 · Try it instantly**")
        st.caption("Load a realistic 16-product demo store — no file needed.")
        if st.button("🚀 Load demo data", type="primary", use_container_width=True, key="welcome_demo"):
            set_data(*sample.demo_data())
            st.rerun()
    with c2:
        st.markdown("**2 · Bring your own data**")
        st.caption("Upload any CSV/Excel from the sidebar — map your columns, even if the headers don't match ours.")
        st.download_button("⬇️ Download template", sample.template_excel_bytes(),
                           "stock_sync_template.xlsx", use_container_width=True, key="welcome_tpl")
    with c3:
        st.markdown("**3 · Type it in**")
        st.caption("Start from a blank table and add products by hand.")
        if st.button("✏️ Start manual entry", use_container_width=True, key="welcome_manual"):
            set_data(sample.template_products().iloc[0:0], sample.empty_demand(), persist=False)
            st.session_state.loaded = True
            st.rerun()


# --------------------------------------------------------------------------
# Dashboard views
# --------------------------------------------------------------------------
def metrics_row(adf: pd.DataFrame) -> None:
    n = len(adf)
    oos = int((adf["status"] == "out").sum())
    fill = adf["fulfillment_rate"].mean() if n else 0
    reorder = int((adf["suggested_order"] > 0).sum())
    value = adf["inventory_value"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total SKUs", n)
    c2.metric("Avg fulfillment", f"{fill:.1f}%")
    c3.metric("Needs reorder", reorder, f"{oos} out of stock", delta_color="inverse")
    c4.metric("Inventory value", f"${value/1000:.1f}K")


def render_insights(adf: pd.DataFrame, accuracy: dict | None) -> None:
    cards = insights.compute(adf, accuracy)
    if not cards:
        return
    st.markdown("##### 🔑 Key insights")
    for i in range(0, len(cards), 2):
        cols = st.columns(2)
        for col, c in zip(cols, cards[i:i + 2]):
            color = SEV_COLOR.get(c["severity"], ACCENT)
            col.markdown(
                f"""<div class="prodcard" style="border-left:3px solid {color}">
                  <div style="font-size:13px;font-weight:600">{c['icon']} {c['headline']}</div>
                  <div class="muted" style="margin-top:4px">{c['detail']}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def view_dashboard(adf: pd.DataFrame, weeks: list[int], accuracy: dict | None = None) -> None:
    if st.session_state.get("data_note"):
        st.caption(f"ℹ️ {st.session_state.data_note}")
    render_insights(adf, accuracy)
    st.write("")
    metrics_row(adf)
    st.write("")
    left, right = st.columns([2, 1])

    with left:
        st.markdown("##### Demand vs fulfillment")
        demand = st.session_state.demand
        if not demand.empty:
            agg = demand.groupby("week").agg(demand=("demand", "sum"),
                                             fulfilled=("fulfilled", "sum")).reset_index()
            fig = go.Figure()
            fig.add_scatter(x=agg["week"], y=agg["demand"], name="Demand", mode="lines+markers",
                            line=dict(color=ACCENT, width=2), fill="tozeroy", fillcolor="rgba(0,229,255,0.08)")
            if agg["fulfilled"].notna().any():
                fig.add_scatter(x=agg["week"], y=agg["fulfilled"], name="Fulfilled", mode="lines+markers",
                                line=dict(color=GREEN, width=2), fill="tozeroy", fillcolor="rgba(0,230,118,0.08)")
            st.plotly_chart(style_fig(fig), use_container_width=True)
        else:
            st.info("No weekly demand history — add it for forecasts and fulfillment trends.")

    with right:
        st.markdown("##### Inventory value by category")
        cat = adf.groupby("category")["inventory_value"].sum().reset_index()
        fig = go.Figure(go.Pie(labels=cat["category"], values=cat["inventory_value"], hole=0.55,
                               marker=dict(colors=SERIES[:len(cat)]), textinfo="percent"))
        st.plotly_chart(style_fig(fig, 240), use_container_width=True)

    st.markdown("##### Product overview")
    show = adf[["name", "category", "current_stock", "avg_demand", "forecast_total",
                "fulfillment_rate", "status_label", "suggested_order"]].copy()
    st.dataframe(
        show, use_container_width=True, hide_index=True,
        column_config={
            "name": "Product", "category": "Category",
            "current_stock": "Stock", "avg_demand": "Avg/wk",
            "forecast_total": st.column_config.NumberColumn("Forecast", help="Total forecast over the horizon"),
            "fulfillment_rate": st.column_config.ProgressColumn("Fulfillment", min_value=0, max_value=100, format="%.0f%%"),
            "status_label": "Status",
            "suggested_order": st.column_config.NumberColumn("Reorder", help="Suggested order quantity"),
        },
    )


def view_inventory(adf: pd.DataFrame) -> None:
    for cat in sorted(adf["category"].unique()):
        sub = adf[adf["category"] == cat]
        st.markdown(f"##### {cat}  ·  <span class='muted'>{len(sub)} products</span>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, (_, p) in enumerate(sub.iterrows()):
            with cols[i % 3]:
                c = STATUS_COLOR[p["status"]]
                pct = min(100, (p["current_stock"] / p["max_stock"] * 100) if p["max_stock"] else 0)
                st.markdown(
                    f"""<div class="prodcard">
                      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
                        <strong style="font-size:14px">{p['name']}</strong> {badge(p['status'], p['status_label'])}
                      </div>
                      <div style="display:flex;gap:18px;margin-top:10px">
                        <div><div class="muted">STOCK</div><div style="font-size:18px;font-weight:700">{p['current_stock']}</div></div>
                        <div><div class="muted">AVG/WK</div><div style="font-size:18px;font-weight:700">{p['avg_demand']:g}</div></div>
                        <div><div class="muted">FILL</div><div style="font-size:18px;font-weight:700">{p['fulfillment_rate']:.0f}%</div></div>
                      </div>
                      <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{c}"></div></div>
                    </div>""",
                    unsafe_allow_html=True,
                )


def view_forecast(adf: pd.DataFrame, weeks: list[int], accuracy: dict | None = None) -> None:
    if accuracy and accuracy.get("mae") is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Forecast MAE", f"{accuracy['mae']} units",
                  help=f"Backtested on the last {accuracy['holdout']} weeks, {accuracy['products']} SKUs.")
        if accuracy.get("naive_mae"):
            lift = (accuracy["naive_mae"] - accuracy["mae"]) / accuracy["naive_mae"] * 100
            c2.metric("vs naive baseline", f"{lift:+.0f}%", help="Improvement over carrying last week's value forward.")
        if accuracy.get("mape") is not None:
            c3.metric("MAPE", f"{accuracy['mape']}%", help="High for intermittent SKU demand — MAE is the more reliable read here.")

    big = len(adf) > 20
    st.markdown("##### Aggregate forecast" + ("  ·  top 15 SKUs" if big else ""))
    horizon = st.session_state.settings.forecast_weeks
    fc_weeks = [f"+{i}" for i in range(1, horizon + 1)]
    stack = adf.sort_values("avg_demand", ascending=False).head(15) if big else adf
    fig = go.Figure()
    for i, (_, p) in enumerate(stack.iterrows()):
        fig.add_scatter(x=fc_weeks, y=p["forecast"], name=p["name"], mode="lines",
                        stackgroup="one", line=dict(width=0.5, color=SERIES[i % len(SERIES)]))
    st.plotly_chart(style_fig(fig, 320), use_container_width=True)

    st.markdown("##### Demand intensity heatmap" + ("  ·  top 30 SKUs" if big else ""))
    demand = st.session_state.demand
    if not demand.empty:
        keep = adf.sort_values("avg_demand", ascending=False).head(30)["product_id"] if big else adf["product_id"]
        sub = demand[demand["product_id"].isin(keep)]
        pivot = sub.pivot_table(index="product_id", columns="week", values="demand", aggfunc="sum").fillna(0)
        names = adf.set_index("product_id")["name"]
        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=[f"Wk {c}" for c in pivot.columns],
            y=[names.get(idx, idx) for idx in pivot.index],
            colorscale=[[0, "#0D1321"], [1, ACCENT]], showscale=False,
        ))
        st.plotly_chart(style_fig(fig, max(220, 22 * len(pivot))), use_container_width=True)

    st.markdown("##### Per-product forecast  ·  top movers")
    top = adf.sort_values("avg_demand", ascending=False).head(6)
    cols = st.columns(2)
    for i, (_, p) in enumerate(top.iterrows()):
        with cols[i % 2]:
            st.markdown(f"**{p['name']}**  ·  <span class='muted'>μ={p['avg_demand']:g}  σ={p['demand_std']:g}</span>", unsafe_allow_html=True)
            hist = p["history"]
            x_hist = list(range(1, len(hist) + 1))
            x_fc = list(range(len(hist) + 1, len(hist) + 1 + len(p["forecast"])))
            fig = go.Figure()
            fig.add_scatter(x=x_hist, y=hist, name="Actual", line=dict(color=SERIES[i % len(SERIES)], width=2))
            fig.add_bar(x=x_fc, y=p["forecast"], name="Forecast", marker_color=SERIES[i % len(SERIES)], opacity=0.5)
            st.plotly_chart(style_fig(fig, 160), use_container_width=True, key=f"fc_{p['product_id']}")


def view_alerts(adf: pd.DataFrame) -> None:
    alerts = adf[(adf["suggested_order"] > 0) | (adf["status"] != "healthy")]
    if alerts.empty:
        st.success("✅ All inventory levels are healthy — no reorder actions needed.")
        return
    st.caption(f"{len(alerts)} products need attention, sorted by urgency.")
    for _, p in alerts.iterrows():
        c = STATUS_COLOR[p["status"]]
        wks = "∞" if p["weeks_to_stockout"] == float("inf") else f"{p['weeks_to_stockout']:g}"
        order = f"<strong style='color:{ACCENT}'>Order {p['suggested_order']}</strong>" if p["suggested_order"] > 0 else ""
        st.markdown(
            f"""<div class="prodcard" style="border-left:3px solid {c};display:flex;justify-content:space-between;align-items:center">
              <div>
                <strong>{p['name']}</strong> &nbsp; {badge(p['status'], p['status_label'])}
                <div class="muted" style="margin-top:4px">{p['current_stock']} units · {wks} wks to stockout ·
                {p['lead_time_days']}d lead · reorder point {p['reorder_point']:g} · safety stock {p['safety_stock']:g}</div>
              </div>
              <div>{order}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def view_manage() -> None:
    st.markdown("##### Products")
    st.caption("Edit cells, add rows (＋ at the bottom), or delete them, then save.")
    edited = st.data_editor(
        st.session_state.products, num_rows="dynamic", use_container_width=True, hide_index=True,
        key="prod_editor",
        column_config={
            "product_id": st.column_config.NumberColumn("ID"),
            "unit_cost": st.column_config.NumberColumn("Unit cost", format="$%.2f"),
        },
    )
    with st.expander("Weekly demand history (optional)"):
        st.caption("Long format: one row per product per week.")
        edited_d = st.data_editor(st.session_state.demand, num_rows="dynamic",
                                  use_container_width=True, hide_index=True, key="dem_editor")
    if st.button("💾 Save changes", type="primary"):
        set_data(edited, edited_d)
        st.toast("Saved")
        st.rerun()


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------
if st.session_state.pending is not None:
    mapping_screen(st.session_state.pending)
elif not st.session_state.loaded:
    welcome_screen()
else:
    products = st.session_state.products
    if products.empty:
        st.title("📦 Stock Sync")
        st.info("No products yet — add some in the **Manage data** tab below, or load demo data from the sidebar.")
        view_manage()
    else:
        adf = forecasting.analyze(products, st.session_state.demand, st.session_state.settings)
        accuracy = forecasting.backtest(st.session_state.demand, st.session_state.settings)
        weeks = sorted(st.session_state.demand["week"].unique()) if not st.session_state.demand.empty else []
        tabs = st.tabs(["📊 Dashboard", "📋 Inventory", "📈 Forecast", "🔔 Alerts", "✏️ Manage data"])
        with tabs[0]:
            view_dashboard(adf, weeks, accuracy)
        with tabs[1]:
            view_inventory(adf)
        with tabs[2]:
            view_forecast(adf, weeks, accuracy)
        with tabs[3]:
            view_alerts(adf)
        with tabs[4]:
            view_manage()
