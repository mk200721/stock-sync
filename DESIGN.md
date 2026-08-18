# Stock Sync — Design Doc: Insight Layer + Real Data

> Output of an office-hours session (2026-06-23). Goal: make Stock Sync a
> portfolio project that gets Mahesh hired for a **data / business analyst** role.

## Verdict

Good project, currently at ~60% of its hiring value. Its strength is that it
solves a *legible business problem* (what to reorder, before stocking out) that
a hiring manager understands instantly — better than a generic Kaggle notebook
or CRUD app. The gap: it currently reads as "I built a dashboard" rather than
"I can do the analyst job."

## Gaps this design closes

1. **No "so what."** App shows numbers, not the takeaway an analyst is paid for.
2. **Fake data.** Synthetic demo is right for onboarding, but a portfolio needs
   proof of wrestling real, messy data.
3. **Forecast never validated.** No accuracy number = decoration, not rigor.

(SQL is the 4th gap — deferred to Phase 2 below, not done at the same time.)

## Chosen direction: Insight Layer + Real Data

Three additions, each reusing the existing engine/UI:

### 1. Real dataset through the existing column mapping
- Load a real Kaggle/UCI retail dataset (e.g. "retail store inventory",
  UCI "Online Retail") via the column-mapping flow already built.
- Doubles as proof the flexible ingestion survives real-world headers.

### 2. `Key Insights` panel (the analyst muscle)
Auto-generate 3–5 plain-English findings at the top of the dashboard:
- Total capital tied up in inventory.
- $ sitting in **overstock** (stock far above what demand justifies).
- Named SKUs that **stock out within N weeks**.
- **Dead stock** — SKUs with ~zero demand.
- Cash freed if inventory is right-sized to reorder points.

### 3. Forecast backtest
- Hold out the last 4 weeks, forecast them with the existing methods, compute
  **MAE / MAPE**, and display the accuracy. One honest number signals rigor.

### Deliverable: README case study
> "Analyzed [dataset]: $X in overstock, Y SKUs at stockout risk, forecast
> accuracy Z% MAPE, recommended reorders free $W."

With screenshots + the live (Streamlit Cloud) link. This paragraph is the
interview opener.

## Phase 2 (later, not now): SQL backend
Move data into SQLite/Postgres, write the analytics as SQL views shown in the
repo. Hits the #1 analyst job keyword. Do this only after Phase 1 ships — not
in parallel.

## Alternatives considered (and why not now)
- **Reframe as a decision/what-if tool** (service-level scenarios, weekly reorder
  report): good, but more build and doesn't fix the real-data / validation gaps.
- **Ship as-is, polish only**: cheapest, but leaves it a "nice dashboard" and
  closes none of the analyst-specific gaps.

## The Assignment (do before building)
Pick **one** real retail/inventory dataset. Open it in a spreadsheet and find
**one real insight by hand** — e.g. *"SKU 4023 holds 800 units and sells 5/week
— 3 years of stock."* That sentence proves analyst thinking and becomes the
project headline. Bring the dataset + the sentence; then build the insight layer
around it.

## Builder signals observed
Shipped a working app (agency); designed around the user's cold-start problem
unprompted (product sense); took critical feedback without defensiveness. These
are the traits that get people hired — the project is the vehicle to show them.
