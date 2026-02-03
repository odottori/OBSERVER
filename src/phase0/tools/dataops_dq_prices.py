"""DataOps: price Data Quality (halt-aware) runner.

Usage:
  <PY> -m src.tools.dataops_dq_prices --db data/sentinel_alpha.db --asof 2026-01-30
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from src.dataops.dq_prices import run_price_data_quality
from src.db.migrate import cli_migrate


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def _default_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"DQ_PRICES_{ts}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="dataops_dq_prices", description="PHASE1 DataOps: DQ prices (halt-aware)")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    ap.add_argument("--run-id", default=None, help="Run id (default: auto)")
    ap.add_argument("--asof", default=None, help="Asof date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--window-days", type=int, default=365, help="Lookback window in calendar days")
    ap.add_argument("--severity-missing", default="WARN", help="Severity for PRICE_MISSING findings")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    db_path = _normalize_db_path(args.db_path)
    cli_migrate(db_path)

    import duckdb

    con = duckdb.connect(db_path, read_only=False)
    try:
        run_id = str(args.run_id or _default_run_id()).strip()
        asof = pd.to_datetime(args.asof, errors="coerce").date() if args.asof else datetime.now(timezone.utc).date()

        res = run_price_data_quality(
            con,
            run_id=run_id,
            asof_date=asof,
            window_days=int(args.window_days),
            severity_missing=str(args.severity_missing).strip().upper(),
        )

        print(res.status)
        print(res.message)
        print(f"missing_tickers={res.missing_tickers} stale_tickers={res.stale_tickers} invalid_rows={res.invalid_rows}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
