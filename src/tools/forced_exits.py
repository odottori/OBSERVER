"""Inspect fallback / forced exits in audit_trades.

Exit reasons:
- FALLBACK_LAST_PRICE
- MARK_TO_MARKET_END_OF_DATA

If `exit_reason` exists, it is treated as the primary classifier.
Use `--include-mtm` to include MARK_TO_MARKET_END_OF_DATA.
Use `--include-flagged` to additionally include legacy flagged rows
(exit_is_fallback/forced_exit) even when exit_reason is inconsistent.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def _has_column(con: Any, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info('{table}')").fetchall()
    return any(r[1] == col for r in rows)


def _latest_success_run_id(con: Any) -> str | None:
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


def _forced_predicate(
    has_exit_reason: bool,
    has_exit_is_fallback: bool,
    has_forced_exit: bool,
    include_mtm: bool,
    include_flagged: bool,
) -> str:
    parts: list[str] = []

    if has_exit_reason:
        if include_mtm:
            parts.append("exit_reason IN ('FALLBACK_LAST_PRICE','MARK_TO_MARKET_END_OF_DATA')")
        else:
            parts.append("exit_reason = 'FALLBACK_LAST_PRICE'")

        if include_flagged:
            if has_exit_is_fallback:
                parts.append("exit_is_fallback = TRUE")
            if has_forced_exit:
                parts.append("forced_exit = 1")
    else:
        # Legacy schema: rely on flags only.
        if has_exit_is_fallback:
            parts.append("exit_is_fallback = TRUE")
        if has_forced_exit:
            parts.append("forced_exit = 1")

    if not parts:
        return "1=0"

    return "(" + " OR ".join(parts) + ")"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="forced_exits", description="Inspect fallback/forced exits")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    ap.add_argument(
        "--run-id",
        dest="run_id",
        default="",
        help="Run identifier (default: latest SUCCESS run)",
    )
    ap.add_argument("--limit", type=int, default=50, help="Max detail rows to print (default: 50)")
    ap.add_argument("--details", action="store_true", help="Print detail rows from audit_trades")
    ap.add_argument("--gaps", action="store_true", help="Also print matching rows from data_gaps")
    ap.add_argument(
        "--include-mtm",
        action="store_true",
        help="Include MARK_TO_MARKET_END_OF_DATA exits in addition to fallback",
    )
    ap.add_argument(
        "--include-flagged",
        action="store_true",
        help="Also include rows flagged via exit_is_fallback/forced_exit even if exit_reason differs",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    import duckdb

    db_path = _normalize_db_path(args.db_path)
    con = duckdb.connect(db_path)
    try:
        has_exit_reason = _has_column(con, "audit_trades", "exit_reason")
        has_exit_is_fallback = _has_column(con, "audit_trades", "exit_is_fallback")
        has_forced_exit = _has_column(con, "audit_trades", "forced_exit")

        run_id = (args.run_id or "").strip() or _latest_success_run_id(con)
        if not run_id:
            print("No SUCCESS runs found in audit_runs.")
            raise SystemExit(2)

        pred = _forced_predicate(
            has_exit_reason,
            has_exit_is_fallback,
            has_forced_exit,
            include_mtm=args.include_mtm,
            include_flagged=args.include_flagged,
        )

        # Summary
        if has_exit_reason:
            reason_expr = "exit_reason"
        elif has_exit_is_fallback or has_forced_exit:
            reason_expr = "'FALLBACK_LAST_PRICE'"
        else:
            reason_expr = "NULL"

        df_sum = con.execute(
            f"""
            SELECT {reason_expr} AS exit_reason, COUNT(*) AS n
            FROM audit_trades
            WHERE run_id = ? AND {pred}
            GROUP BY 1
            ORDER BY n DESC, exit_reason
            """,
            [run_id],
        ).fetchdf()

        total = int(df_sum["n"].sum()) if not df_sum.empty else 0
        print(f"DB: {db_path}")
        print(f"run_id: {run_id}")
        print(f"exit exceptions: {total}")
        print(df_sum)

        # Diagnostics: exit_reason x exit_is_fallback (and mismatch warnings)
        if has_exit_reason and has_exit_is_fallback:
            df_xtab = con.execute(
                f"""
                SELECT
                    COALESCE(exit_reason,'(null)') AS exit_reason,
                    exit_is_fallback,
                    COUNT(*) AS n
                FROM audit_trades
                WHERE run_id = ? AND {pred}
                GROUP BY 1,2
                ORDER BY exit_reason, exit_is_fallback
                """,
                [run_id],
            ).fetchdf()
            print("\nexit_reason x exit_is_fallback")
            print(df_xtab)

            mism = con.execute(
                """
                SELECT COUNT(*)
                FROM audit_trades
                WHERE run_id = ?
                  AND exit_is_fallback = TRUE
                  AND (exit_reason IS NULL OR exit_reason NOT IN ('FALLBACK_LAST_PRICE','MARK_TO_MARKET_END_OF_DATA'))
                """,
                [run_id],
            ).fetchone()[0]
            mism_n = int(mism or 0)
            if mism_n > 0 and not args.include_flagged:
                print(
                    f"\nWARNING: found {mism_n} rows with exit_is_fallback=TRUE but exit_reason not FALLBACK_LAST_PRICE."
                )
                print("         Use --include-flagged to inspect legacy/inconsistent rows.")

        # Details
        if args.details:
            detail_cols = [
                "trade_id",
                "ticker",
                "signal_date",
                "buy_date",
                "sell_date",
                "buy_price",
                "sell_price",
                "gross_return_pct",
                "cost_pct",
                "net_return_pct",
                "exec_shift_sessions",
                "exit_shift_sessions",
                "halt_reason",
                "market",
                "universe_id",
                "instrument_type",
                "ftt_pct",
            ]

            table_cols = {r[1] for r in con.execute("PRAGMA table_info('audit_trades')").fetchall()}
            detail_cols = [c for c in detail_cols if c in table_cols]

            if has_exit_is_fallback and "exit_is_fallback" not in detail_cols:
                detail_cols.append("exit_is_fallback")
            if has_forced_exit and "forced_exit" not in detail_cols:
                detail_cols.append("forced_exit")
            if has_exit_reason and "exit_reason" not in detail_cols:
                detail_cols.append("exit_reason")
            if not has_exit_reason:
                detail_cols.append("'FALLBACK_LAST_PRICE' AS exit_reason")

            select_list = ",\n        ".join(detail_cols)
            df_det = con.execute(
                f"""
                SELECT
                    {select_list}
                FROM audit_trades
                WHERE run_id = ? AND {pred}
                ORDER BY sell_date DESC NULLS LAST, ticker
                LIMIT {int(args.limit)}
                """,
                [run_id],
            ).fetchdf()

            print("\nDetail rows")
            print(df_det)

        # Related data_gaps
        if args.gaps:
            try:
                df_gaps = con.execute(
                    f"""
                    SELECT
                        g.ticker,
                        g.provider,
                        g.status,
                        COALESCE(g.error,'') AS error,
                        g.rows_inserted,
                        g.requested_at
                    FROM data_gaps g
                    WHERE g.run_id = ?
                      AND g.ticker IN (
                          SELECT DISTINCT ticker
                          FROM audit_trades
                          WHERE run_id = ? AND {pred}
                      )
                    ORDER BY g.ticker, g.provider
                    """,
                    [run_id, run_id],
                ).fetchdf()
                print("\nData gaps")
                print(df_gaps)
            except Exception as e:
                print("\nData gaps: (table missing or query failed)")
                print(str(e))

    finally:
        con.close()


if __name__ == "__main__":
    main()
