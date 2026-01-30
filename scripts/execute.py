#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4


def ensure_sys_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def _parse_date(s: str) -> date:
    return date.fromisoformat(str(s).strip())


def main(argv: list[str] | None = None) -> int:
    ensure_sys_path()

    ap = argparse.ArgumentParser(prog="execute", description="Execution runner (paper broker)")
    ap.add_argument("--db", dest="db_path", default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"))
    ap.add_argument("--paper", action="store_true", help="Run paper broker and write execution_* tables")
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--asof-date", default="", help="Override ranking date (YYYY-MM-DD)")
    ap.add_argument("--run-id", default=os.environ.get("SENTINEL_RUN_ID", ""))
    args = ap.parse_args(argv)

    from src.db.connection import DbConfig, connect
    from src.db.migrate import ensure_schema
    from src.execution.paper_broker import execute_paper_broker

    run_id = (args.run_id or "").strip() or uuid4().hex
    db_path = args.db_path

    con = connect(DbConfig(db_path=db_path))
    try:
        ensure_schema(con)

        asof_date = _parse_date(args.asof_date) if str(args.asof_date).strip() else None

        if not args.paper:
            raise SystemExit("Unsupported mode: use --paper")

        res = execute_paper_broker(con, run_id=run_id, asof_date=asof_date, top_n=args.top_n)
        print(f"OK: paper execution completed run_id={res.run_id} asof_date={res.asof_date} orders={res.orders_written} fills={res.fills_written}")
    finally:
        try:
            con.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
