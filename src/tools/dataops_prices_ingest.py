"""DataOps: incremental prices ingest (PHASE1).

Usage:
  <PY> -m src.tools.dataops_prices_ingest --db data/sentinel_alpha.db --asof 2026-01-30

By default this stays offline (respects SENTINEL_OFFLINE).
Use --online to explicitly allow online backfill providers.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def _default_run_id(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{ts}"


def _as_date(v: str):
    d = pd.to_datetime(v, errors="coerce")
    if pd.isna(d):
        raise ValueError(f"invalid date: {v}")
    return d.date()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="dataops_prices_ingest", description="DataOps incremental prices ingest")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database",
    )
    ap.add_argument("--run-id", default=None, help="run_id to attach to data_gaps / audit (default: auto)")
    ap.add_argument("--asof", default=None, help="As-of date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--universe-id", default="ALL", help="Universe id (default: ALL)")
    ap.add_argument("--lookback-days", type=int, default=45, help="Lookback window for refresh (default: 45)")
    ap.add_argument("--start-date", default=None, help="Force start date YYYY-MM-DD for all tickers")
    ap.add_argument("--max-window-days", type=int, default=180, help="Max provider window (default: 180)")
    ap.add_argument("--online", action="store_true", help="Allow online ingestion providers")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    import duckdb

    from src.db.migrate import cli_migrate
    from src.dataops.prices_ingest import ingest_prices_incremental

    db_path = _normalize_db_path(args.db_path)
    cli_migrate(db_path)

    run_id = args.run_id or _default_run_id("DATAOPS_PRICES_INGEST")

    if args.asof:
        asof = _as_date(args.asof)
    else:
        asof = datetime.now(timezone.utc).date()

    start_date = _as_date(args.start_date) if args.start_date else None

    con = duckdb.connect(db_path, read_only=False)
    try:
        res = ingest_prices_incremental(
            con,
            run_id=run_id,
            asof_date=asof,
            universe_id=str(args.universe_id),
            lookback_days=int(args.lookback_days),
            start_date=start_date,
            max_window_days=int(args.max_window_days),
            online=bool(args.online),
        )
    finally:
        try:
            con.close()
        except Exception:
            pass

    print(res.status)
    print(res.message)
    print(f"tickers={res.tickers} attempted={res.attempted} total_rows_upserted={res.total_rows_upserted}")


if __name__ == "__main__":
    main()
