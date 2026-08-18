# Datasets

Stock Sync works on **any** product/sales data via the in-app column mapper, and
ships with synthetic demo data so you can try it with zero setup. The tables below
are the *real* retail datasets used to build and stress-test it.

## What's in the repo

| File | Source | Real company? | License | Committed? |
|---|---|---|---|---|
| `online_retail_ii_sample.csv` | [Online Retail II (UCI)](https://huggingface.co/datasets/mariorivas17/online_retail) | ✅ UK online gift retailer | **CC BY 4.0** | ✅ yes (30-day, ~88K-row sample) |
| *(built-in)* synthetic demo | `optimizer/sample.py` | — | this repo's license | ✅ generated in code |

Only the CC BY 4.0 sample is committed, because redistributing data requires a
license that permits it. Everything else is fetched on demand (below).

## Fetch the larger / restricted datasets

```bash
python scripts/fetch_datasets.py            # all of them
python scripts/fetch_datasets.py dataco     # just one
```

| Key | Source | Real company? | Rows | Notes / license |
|---|---|---|---|---|
| `online_retail` | [Online Retail II (UCI)](https://huggingface.co/datasets/mariorivas17/online_retail) | ✅ UK retailer | 1.1M | Full set. CC BY 4.0. |
| `dataco` | [DataCo Smart Supply Chain](https://huggingface.co/datasets/alalfi/SupplyChainDataset) | ✅ real orders | 180K | Real **lead times**, profit margins, late-delivery flags. Masked PII stripped on fetch. |
| `dirty_retail` | [Retail Store Sales (dirty)](https://huggingface.co/datasets/jason1966/ahmedmohamed2003_retail-store-sales-dirty-for-data-cleaning) | mixed | 12.5K | Deliberately messy — used for the cleaning case study. License unspecified; demo/research use only, not committed. |
| `grocery` | [Corporación Favorita](https://huggingface.co/datasets/dunnowho/grocery-sales-forecasting) | ✅ Ecuador grocery chain | 92M (1 shard ≈ 9M fetched) | Kaggle competition data — **do not redistribute**; fetch yourself. |

## Attribution

**Online Retail II** — Dr Daqing Chen, London South Bank University. From the UCI
Machine Learning Repository, licensed CC BY 4.0. A real online retail transaction
log (Dec 2009 – Dec 2011) for a UK-based registered non-store online retailer.

## Loading into Stock Sync

- **Built-in demo** — click *Load demo data*. No file needed.
- **Any CSV/Excel** — upload from the sidebar and map your columns; headers don't
  have to match ours.
- **The dirty retail set** — has a dedicated cleaner (`optimizer/retail.py`) wired
  to the *Load real retail data* button once fetched.
