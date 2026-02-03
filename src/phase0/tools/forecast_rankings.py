"""Wave 6: Forecasts, Stars & Ranking (CLI tool).

Usage
-----
<PY> -m src.tools.forecast_rankings --db data/sentinel_alpha.db --universe-id ALL

When executed with a run_id (either via --run-id or SENTINEL_RUN_ID), artifacts are named:
  reports/FORECAST_RANKING_<run_id>.{json,md}

Otherwise artifacts are named by asof_date:
  reports/FORECAST_RANKING_<YYYY-MM-DD>.{json,md}

Constraints
-----------
- Offline-by-default: no network calls
- Deterministic output
- No future leak: calibration uses audit_trades.signal_date < asof_date
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import duckdb

from src.forecast.ranking import (
    DEFAULT_TOP_N,
    determine_asof_date,
    generate_forecast_ranking,
    write_forecast_ranking_artifacts,
)


def _parse_asof(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"invalid --asof date: {s} ({e})")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="forecast_rankings", description="Wave 6: Forecasts, Stars & Ranking")
    p.add_argument("--db", "--db-path", dest="db_path", default="data/sentinel_alpha.db", help="Path to DuckDB db")
    p.add_argument("--universe-id", default="ALL", help="Universe id (default: ALL)")
    p.add_argument("--asof", default="", help="As-of date YYYY-MM-DD (default: max(recs.date))")
    p.add_argument("--top-n", type=int, default=int(DEFAULT_TOP_N), help=f"Top N rows in markdown (default: {DEFAULT_TOP_N})")
    p.add_argument(
        "--run-id",
        default="",
        help="Optional run_id for artifact naming (default: SENTINEL_RUN_ID env var if set)",
    )
    p.add_argument(
        "--reports-dir",
        default="reports",
        help="Output directory for artifacts (default: reports)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])

    run_id = (args.run_id or os.environ.get("SENTINEL_RUN_ID") or "").strip() or None
    universe_id = (args.universe_id or "ALL").strip() or "ALL"
    top_n = max(1, int(args.top_n))

    asof = _parse_asof(args.asof)

    con = duckdb.connect(database=args.db_path, read_only=False)
    try:
        if asof is None:
            asof = determine_asof_date(con, universe_id)
        if asof is None:
            raise SystemExit("[ERROR] no recs rows found; cannot infer asof_date")

        obj = generate_forecast_ranking(
            con,
            universe_id=universe_id,
            asof_date=asof,
            top_n=top_n,
            run_id=run_id,
        )

        paths = write_forecast_ranking_artifacts(
            obj,
            reports_dir=args.reports_dir,
            run_id=run_id,
            asof_date=asof.isoformat(),
            top_n=top_n,
        )

        print("[PASS] forecast_rankings")
        print(f"  universe_id={universe_id}; asof_date={asof.isoformat()}; run_id={run_id or '(none)'}")
        print(f"  json={paths.get('json')}")
        print(f"  md={paths.get('md')}")
        print(f"  latest_json={paths.get('latest_json')}")
        raise SystemExit(0)

    except SystemExit:
        raise
    except Exception as e:
        print("[ERROR] forecast_rankings:", str(e))
        raise SystemExit(2)
    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
