"""DataOps: status snapshot (halts/closures/prices/DQ).

Usage:
  <PY> -m src.tools.dataops_status --db data/sentinel_alpha.db

This tool is intentionally read-only.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="dataops_status", description="DataOps status snapshot")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    import duckdb

    db_path = _normalize_db_path(args.db_path)
    con = duckdb.connect(db_path, read_only=True)
    try:
        print(f"DB: {db_path}")

        def _safe_scalar(sql: str, params=None):
            try:
                row = con.execute(sql, params or []).fetchone()
                return row[0] if row else None
            except Exception:
                return None

        print("\n[halts]")
        print(f"market_halts: {_safe_scalar('SELECT COUNT(*) FROM market_halts')}")
        print(f"ticker_halts: {_safe_scalar('SELECT COUNT(*) FROM ticker_halts')}")

        print("\n[prices]")
        print(f"prices rows: {_safe_scalar('SELECT COUNT(*) FROM prices')}")
        print(f"tickers: {_safe_scalar('SELECT COUNT(DISTINCT ticker) FROM prices')}")
        print(f"min(date): {_safe_scalar('SELECT MIN(date) FROM prices')}")
        print(f"max(date): {_safe_scalar('SELECT MAX(date) FROM prices')}")

        print("\n[data_gaps]")
        print(f"data_gaps rows: {_safe_scalar('SELECT COUNT(*) FROM data_gaps')}")
        print(f"last requested_at: {_safe_scalar('SELECT MAX(requested_at) FROM data_gaps')}")

        print("\n[dq]")
        has_dq = bool(_safe_scalar("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='dq_runs'"))
        if not has_dq:
            print("dq tables: (missing)")
        else:
            print(f"dq_runs: {_safe_scalar('SELECT COUNT(*) FROM dq_runs')}")
            print(f"dq_findings: {_safe_scalar('SELECT COUNT(*) FROM dq_findings')}")
            print(f"dq_metrics_daily: {_safe_scalar('SELECT COUNT(*) FROM dq_metrics_daily')}")
            q = "SELECT MAX(finished_at) FROM dq_runs WHERE kind='DQ_PRICES'"
            print(f"last dq run finished_at: {_safe_scalar(q)}")
    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
