"""Verify Definition-of-Done gates for a given audit run.

Usage:
    <PY> -m src.tools.verify_run --db data/sentinel_alpha.db
    <PY> -m src.tools.verify_run --db data/sentinel_alpha.db --run-id <RUN_ID>

Exit codes:
    0 PASS
    1 FAIL
    2 No SUCCESS run found
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
    ap = argparse.ArgumentParser(prog="verify_run", description="Verify DoD gates for a run")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    ap.add_argument(
        "--run-id",
        dest="run_id",
        default=os.environ.get("SENTINEL_RUN_ID", ""),
        help="Run identifier (default: latest SUCCESS run)",
    )
    return ap.parse_args(argv)


def _latest_success_run_id(con) -> str | None:
    row = con.execute(
        """
        SELECT run_id
        FROM audit_runs
        WHERE status = 'SUCCESS'
        ORDER BY finished_at DESC NULLS LAST, started_at DESC NULLS LAST
        LIMIT 1
        """
    ).fetchone()
    return row[0] if row else None


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    import duckdb

    db_path = _normalize_db_path(args.db_path)
    con = duckdb.connect(db_path)
    try:
        rid = (args.run_id or "").strip() or _latest_success_run_id(con)
        if not rid:
            print("No SUCCESS runs found in audit_runs.")
            raise SystemExit(2)

        print(f"Verifying run_id: {rid}")

        failures: list[str] = []
        warnings: list[str] = []

        # Gate 1: No NULL buy/sell dates
        null_dates = con.execute(
            """
            SELECT count(*)
            FROM audit_trades
            WHERE run_id = ? AND (buy_date IS NULL OR sell_date IS NULL)
            """,
            [rid],
        ).fetchone()[0]
        if int(null_dates) != 0:
            failures.append(f"audit_trades has {int(null_dates)} rows with NULL buy_date/sell_date")

        # Gate 2: end-of-run positions == 0
        last_pos = con.execute(
            """
            SELECT positions
            FROM audit_equity
            WHERE run_id = ?
            ORDER BY date DESC
            LIMIT 1
            """,
            [rid],
        ).fetchone()
        if last_pos is None:
            failures.append("audit_equity is missing for this run")
        else:
            try:
                if int(last_pos[0]) != 0:
                    failures.append(f"positions at end-of-run is {int(last_pos[0])}, expected 0")
            except Exception:
                warnings.append("Could not parse audit_equity.positions")

        # Gate 3: market/universe_id populated
        null_meta = con.execute(
            """
            SELECT count(*)
            FROM audit_trades
            WHERE run_id = ? AND (market IS NULL OR universe_id IS NULL)
            """,
            [rid],
        ).fetchone()[0]
        if int(null_meta) != 0:
            failures.append(f"audit_trades has {int(null_meta)} rows with NULL market/universe_id")

        # Gate 4: data_gaps coherence
        gaps = con.execute(
            "SELECT count(*) FROM data_gaps WHERE run_id = ?",
            [rid],
        ).fetchone()
        gaps_n = int(gaps[0]) if gaps else 0

        # Gate 4b: fallback exits require data_gaps audit trail
        try:
            fallback_exits = con.execute(
                "SELECT count(*) FROM audit_trades WHERE run_id = ? AND exit_reason = 'FALLBACK_LAST_PRICE'",
                [rid],
            ).fetchone()[0]
            mark_to_market_exits = con.execute(
                "SELECT count(*) FROM audit_trades WHERE run_id = ? AND exit_reason = 'MARK_TO_MARKET_END_OF_DATA'",
                [rid],
            ).fetchone()[0]
            forced_total = int(fallback_exits or 0) + int(mark_to_market_exits or 0)
        except Exception:
            fallback_exits = 0
            mark_to_market_exits = 0
            forced_total = int(
                con.execute(
                    "SELECT count(*) FROM audit_trades WHERE run_id = ? AND exit_is_fallback = TRUE",
                    [rid],
                ).fetchone()[0]
            )

        if int(fallback_exits) > 0 and gaps_n == 0:
            failures.append(
                f"{int(fallback_exits)} fallback exits but 0 data_gaps rows for run_id (expected backfill audit trail)"
            )

        # Gate 5: no open trades
        open_trades = con.execute(
            """
            SELECT count(*)
            FROM audit_trades
            WHERE run_id = ? AND (sell_date IS NULL OR buy_date IS NULL)
            """,
            [rid],
        ).fetchone()[0]
        if int(open_trades) != 0:
            failures.append(f"audit_trades contains {int(open_trades)} open/invalid trades")

        print("\nGates summary")
        print("- NULL dates in audit_trades:", int(null_dates))
        print("- Fallback exits:", int(fallback_exits))
        print("- Mark-to-market exits:", int(mark_to_market_exits))
        print("- Exit exceptions total:", int(forced_total))
        print("- data_gaps rows:", gaps_n)
        if last_pos is not None:
            print("- End positions:", last_pos[0])
        print("- NULL market/universe_id:", int(null_meta))

        if warnings:
            print("\nWarnings")
            for w in warnings:
                print("-", w)

        if failures:
            print("\nFAIL")
            for e in failures:
                print("-", e)
            raise SystemExit(1)

        print("\nPASS")
    finally:
        con.close()


if __name__ == "__main__":
    main()
