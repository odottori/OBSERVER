"""DataOps: sync halts.yml overlay into DB (market_halts + ticker_halts).

Usage:
  <PY> -m src.tools.dataops_sync_halts --db data/sentinel_alpha.db

This is a thin wrapper around `src.dataops.halts_sync.sync_halts_yaml`.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def _default_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"DATAOPS_SYNC_HALTS_{ts}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="dataops_sync_halts", description="Sync halts.yml into DB")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    ap.add_argument("--run-id", default=_default_run_id(), help="Run id (default: generated)")
    ap.add_argument(
        "--yaml",
        dest="yaml_path",
        default=str(_project_root() / "config" / "dataops" / "halts.yml"),
        help="halts.yml path",
    )
    ap.add_argument(
        "--replace",
        dest="replace_previous",
        action="store_true",
        help="Replace previous rows with source=MANUAL:halts.yml (default: true)",
    )
    ap.set_defaults(replace_previous=True)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import duckdb

    from src.db.migrate import cli_migrate
    from src.dataops.halts_sync import sync_halts_yaml

    db_path = _normalize_db_path(args.db_path)
    cli_migrate(db_path)
    con = duckdb.connect(db_path, read_only=False)
    try:
        res = sync_halts_yaml(
            con,
            run_id=str(args.run_id),
            yaml_path=Path(args.yaml_path),
            replace_previous=bool(args.replace_previous),
        )
    finally:
        try:
            con.close()
        except Exception:
            pass

    print(f"status={res.status} market_rows={res.market_rows} ticker_rows={res.ticker_rows}")
    print(res.message)
    return 0 if res.status == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
