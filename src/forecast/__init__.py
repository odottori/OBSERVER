"""Wave 6: Pre-trade forecasts, stars and ranking.

This package is intentionally small and deterministic:
- Offline-by-default (no network calls)
- No schema changes (reads existing DuckDB tables)
- No future leak: calibration uses audit_trades.signal_date < asof_date
"""

from __future__ import annotations

from .ranking import generate_forecast_ranking, write_forecast_ranking_artifacts

__all__ = ["generate_forecast_ranking", "write_forecast_ranking_artifacts"]
