"""Stock Sync — inventory optimization engine.

Pure-Python/pandas analytics so the forecasting and inventory math is testable
on its own, independent of the Streamlit UI.
"""

from . import forecasting, ingest, sample

__all__ = ["forecasting", "ingest", "sample"]
