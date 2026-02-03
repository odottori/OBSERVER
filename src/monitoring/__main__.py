from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def ensure_sys_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def main(argv: list[str] | None = None) -> int:
    ensure_sys_path()

    ap = argparse.ArgumentParser(prog="monitoring", description="Monitoring/TCA v0")
    ap.add_argument("--db", dest="db_path", default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"))
    ap.add_argument("--run-id", default="")
    ap.add_argument("--threshold-bp", type=float, default=10.0)
    args = ap.parse_args(argv)

    from src.phase0.db.connection import DbConfig, connect
    from src.phase0.db.migrate import ensure_schema
    from src.monitoring.tca_report import build_tca_report_text

    con = connect(DbConfig(db_path=args.db_path))
    try:
        ensure_schema(con)
        txt = build_tca_report_text(con, run_id=(args.run_id or '').strip() or None, threshold_cost_drag_bp=float(args.threshold_bp))
        sys.stdout.write(txt)
    finally:
        try:
            con.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
