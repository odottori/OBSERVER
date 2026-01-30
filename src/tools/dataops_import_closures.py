"""DataOps: import/seed historical market closures into market_halts.

Usage:
  <PY> -m src.tools.dataops_import_closures --db data/sentinel_alpha.db

Notes
-----
- Reads config/dataops/borse_chiusure_storiche.csv
- Uses config/dataops/exchange_to_market.yml to map exchange -> market
- Writes compressed intervals into market_halts (source configurable)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from datetime import datetime, timezone


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def _default_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"DATAOPS_CLOSURES_SEED_{ts}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="dataops_import_closures", description="Seed market closures into market_halts")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    ap.add_argument("--run-id", default=None, help="Run id (default: auto)")
    ap.add_argument("--csv", default=None, help="Path to closures CSV (default: config/dataops/borse_chiusure_storiche.csv)")
    ap.add_argument("--mapping", default=None, help="Path to exchange_to_market.yml (default: config/dataops/exchange_to_market.yml)")
    ap.add_argument("--source", default="SEED_CLOSURES_CSV", help="Source label stored in market_halts")
    ap.add_argument("--no-replace", action="store_true", help="Do not delete previous seed rows for the same source")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    import duckdb

    from src.db.migrate import cli_migrate
    from src.dataops.closures_seed import seed_market_halts_from_csv

    db_path = _normalize_db_path(args.db_path)
    cli_migrate(db_path)

    run_id = args.run_id or _default_run_id()

    con = duckdb.connect(db_path, read_only=False)
    try:
        res = seed_market_halts_from_csv(
            con,
            run_id=run_id,
            csv_path=Path(args.csv).resolve() if args.csv else None,
            mapping_path=Path(args.mapping).resolve() if args.mapping else None,
            source=str(args.source).strip(),
            replace_seed=not bool(args.no_replace),
        )
    finally:
        try:
            con.close()
        except Exception:
            pass

    print(res.status)
    print(res.message)
    print(f"rows_inserted={res.rows_inserted} markets={res.markets} run_id={run_id}")


if __name__ == "__main__":
    main()
