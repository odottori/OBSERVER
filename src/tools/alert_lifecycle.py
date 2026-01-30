"""Lifecycle monitor (CLI tool).

Questo tool materializza la vista di lifecycle per gli alert, supportando:
- navigazione temporale (AS-OF / now_date)
- TTL = 0 (tradabile solo nel primo giorno utile dopo il segnale)
- no-future-leak (intended_entry_date usa prezzi <= now_date)

Modalita'
---------
- trading: ignora completamente audit_trades (vista decisionale)
- backtest: include audit_trades e mostra stati di simulazione as-of

Esempi
------
Windows/PowerShell:
  py -3.14 -m src.tools.alert_lifecycle --db data/sentinel_alpha.db --universe-id ALL --now 2026-01-07 --mode trading
  py -3.14 -m src.tools.alert_lifecycle --db data/sentinel_alpha.db --universe-id ALL --now 2026-01-07 --mode backtest
Linux/macOS:
  python -m src.tools.alert_lifecycle --db data/sentinel_alpha.db --universe-id ALL --now 2026-01-07 --mode trading
  python -m src.tools.alert_lifecycle --db data/sentinel_alpha.db --universe-id ALL --now 2026-01-07 --mode backtest
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import duckdb

from src.core.alert_lifecycle import LifecycleParams, compute_alert_lifecycle


def _parse_date(s: str) -> date:
    s2 = str(s).strip()
    try:
        return date.fromisoformat(s2)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"invalid date: {s2} ({e})")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="alert_lifecycle", description="Alert lifecycle (TTL=0, AS-OF navigation)")
    p.add_argument("--db", "--db-path", dest="db_path", default="data/sentinel_alpha.db", help="Path to DuckDB db")
    p.add_argument("--universe-id", default="ALL", help="Universe id (default: ALL)")
    p.add_argument("--now", dest="now", type=_parse_date, required=True, help="AS-OF date YYYY-MM-DD")
    p.add_argument("--lookback-days", type=int, default=14, help="Lookback window in calendar days (default: 14)")
    p.add_argument(
        "--only-today",
        action="store_true",
        help="Restrict to alerts where signal_date == now_date (default: false)",
    )
    p.add_argument(
        "--mode",
        choices=["trading", "backtest"],
        default="trading",
        help="Mode: trading (no audit) or backtest (include audit_trades) (default: trading)",
    )
    p.add_argument("--show", type=int, default=25, help="Show first N rows (default: 25)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])

    include_audit = bool(args.mode == "backtest")

    con = duckdb.connect(database=args.db_path, read_only=True)
    try:
        params = LifecycleParams(
            universe_id=str(args.universe_id),
            now_date=args.now,
            lookback_days=int(args.lookback_days),
            only_signal_date_equals_now=bool(args.only_today),
            include_audit_trades=include_audit,
        )
        df = compute_alert_lifecycle(con, params)

        print("[PASS] alert_lifecycle")
        print(
            "  universe_id={}; now_date={}; lookback_days={}; only_today={}; mode={}".format(
                params.universe_id,
                params.now_date.isoformat(),
                params.lookback_days,
                params.only_signal_date_equals_now,
                args.mode,
            )
        )

        if df is None or df.empty:
            print("  rows=0")
            raise SystemExit(0)

        rows = int(len(df))
        operable = int(df.get("operable_today", 0).sum())
        blocked = int(df.get("tradable_blocked", 0).sum())
        waitlist = int((df["status"] == "WAITLIST").sum())
        expired = int((df["status"] == "EXPIRED").sum())
        tradable = int((df["status"] == "TRADABLE").sum())

        print("  counts:")
        print(f"    total={rows}")
        print(f"    tradable={tradable} (TTL=0: entry window opens only on intended_entry_date)")
        print(f"    operable_today={operable} (TRADABLE + provenance_ok)")
        print(f"    tradable_blocked={blocked} (TRADABLE but provenance not OK)")
        print(f"    waitlist={waitlist}")
        print(f"    expired={expired}")

        if include_audit:
            traded_open = int((df["status"] == "TRADED_OPEN").sum())
            traded_closed = int((df["status"] == "TRADED_CLOSED").sum())
            print(f"    simulated_open_asof={traded_open}")
            print(f"    simulated_closed_asof={traded_closed}")

        n = max(0, int(args.show))
        if n > 0:
            cols = [
                "signal_date",
                "ticker",
                "firm",
                "rating",
                "status",
                "provenance_ok",
                "intended_entry_date",
                "buy_date",
                "sell_date",
                "reason_code",
            ]
            cols = [c for c in cols if c in df.columns]
            print("\n  sample:")
            print(df[cols].head(n).to_string(index=False))

        raise SystemExit(0)

    except SystemExit:
        raise
    except Exception as e:
        print("[ERROR] alert_lifecycle:", str(e))
        raise SystemExit(2)
    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
