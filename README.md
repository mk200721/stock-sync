<div align="center">

# 📦 Stock Sync

### Inventory forecasting & reorder reminders for small businesses

Demand planning for the shops that still track stock by hand — predict inventory
from your weekly usage, and get told when to reorder before you run out.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

</div>

---

## Why it exists

Big retailers have demand-planning teams and six-figure inventory software. The
corner store, the local grocer, the small online seller — they don't. Most track
stock the manual way: a spreadsheet, a paper notebook, or just memory. That leads
to the same two costly problems, over and over:

- **Stockouts** — running out of the things customers actually want to buy.
- **Frozen cash** — money tied up in stock that sits on the shelf and barely moves.

**Stock Sync gives a small business that planning capability with none of the
overhead.** Feed it your weekly usage and it:

- **predicts how long your stock will last** and what the coming weeks of demand look like, and
- **reminds you when — and how much — to reorder**, before you run out.

No ERP, no data team, no setup. Your numbers in, clear decisions out.

## What it does

Stock Sync turns raw product sales into decisions a store owner can act on:

- **Forecasts demand** for every SKU (exponential smoothing, moving average, or seasonal naive).
- **Sizes safety stock & reorder points** from demand variability and lead time.
- **Flags what to do** — reorder now, overstocked, dead stock, about to stock out.
- **Surfaces the "so what"** — auto-written insights like *"half the catalog drives under 20% of revenue"* and *"$23K is tied up in overstock."*
- **Backtests its own accuracy** (MAE / MAPE vs a naive baseline) — no accuracy claims it can't prove.

## Try it in 60 seconds

```bash
git clone https://github.com/mk200721/stock-sync.git && cd stock-sync
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then click **🚀 Load demo data** — the app works instantly, no file needed.
Want real data? Click **🛒 Load real retail data**, or upload your own CSV/Excel
and map the columns (your headers don't have to match).

> 📷 _Add a screenshot or GIF of the dashboard here once deployed._

## No cold-start problem

The original version of this project only worked if you handed it a perfectly
shaped spreadsheet. Stock Sync removes that barrier four ways:

| | |
|---|---|
| 🚀 **Built-in demo** | A realistic store loads on first open — zero setup. |
| 🔀 **Flexible column mapping** | Upload *any* CSV/Excel; it guesses your columns and lets you confirm. |
| ⬇️ **Downloadable template** | A pre-filled example to copy and edit. |
| ✏️ **Manual entry** | Type products in by hand; edits persist between visits. |

## Real datasets to try it with

You can run Stock Sync on genuine retail data, not just the demo. One real,
openly-licensed dataset ships in the repo; the rest fetch on demand:

| Dataset | Real company | License | How to get it |
|---|---|---|---|
| **Online Retail II** | ✅ UK online retailer | CC BY 4.0 | included: `data/online_retail_ii_sample.csv` |
| **DataCo Supply Chain** | ✅ real orders (lead times, profit) | see source | `python scripts/fetch_datasets.py dataco` |
| **Retail Store Sales (dirty)** | messy real-world | demo/research | `python scripts/fetch_datasets.py dirty_retail` |
| **Corporación Favorita** | ✅ Ecuador grocery chain (92M rows) | Kaggle comp. | `python scripts/fetch_datasets.py grocery` |

Full sources, licenses, and attribution: **[data/DATA.md](data/DATA.md)**.

## Case study: cleaning real, messy data

Stock Sync ingests a deliberately dirty 12.5K-row retail dataset end to end — the
kind of analyst work that turns raw data into a recommendation:

1. **Clean.** ~600 rows each missing Price/Quantity/Total are recovered from the
   identity `Price × Quantity = Total` (verified: 0 violations). 1,213 rows missing
   an item code were *tested* — discount rates were identical with/without a code
   and missingness was uniform across all categories, i.e. **missing at random**, a
   system artifact, so they're dropped rather than given a made-up story.
2. **Reshape.** Transactions → weekly demand per SKU.
3. **Find the money.** Half the catalog drives under 20% of revenue; ~$23K sits in
   overstock; a dozen SKUs will stock out before a reorder can arrive.

> **Honest caveat:** datasets that record sales but not on-hand inventory have stock
> simulated from demand (clearly labelled in-app). Lead times, where available
> (DataCo), are real.

## How the math works

All in [`optimizer/`](optimizer/), pure pandas/numpy so it's testable without the UI:

- **Safety stock** = `z · σ · √(lead time)`, with `z` from a configurable service level (90–99%).
- **Reorder point** = `avg demand · lead time + safety stock`.
- **Order quantity** — order-up-to-max when stock crosses the reorder point.
- **Backtest** — hold out the last N weeks, predict them, report MAE/MAPE vs naive.

## Project layout

```
app.py                  Streamlit UI — data sources, insights panel, 5 tabbed views
optimizer/
  forecasting.py        demand stats, forecasting, safety stock, reorder, backtest
  insights.py           auto-generated plain-English business findings
  retail.py             clean + reshape the dirty retail dataset
  ingest.py             read any CSV/Excel + fuzzy column mapping
  sample.py             synthetic demo data + downloadable template
  storage.py            local CSV persistence for manual edits
scripts/fetch_datasets.py   pull the larger real datasets from Hugging Face
data/DATA.md            dataset sources, licenses, attribution
```

## Deploy

Push to GitHub and deploy free on [Streamlit Community Cloud](https://streamlit.io/cloud)
for a shareable public URL. Point it at `app.py`.

## License

Code: [MIT](LICENSE). Datasets: licensed separately by their authors — see
[data/DATA.md](data/DATA.md).
