"""Pre-audit input gates.

Purpose
-------
Fail fast if the audit inputs are inconsistent, before expensive ledger construction:
- Eligible signals (after survivorship + ticker mappings) must reference tickers that have price coverage.

Usage
-----
<PY> -m src.tools.verify_inputs --db data/sentinel_alpha.db --universe-id ALL

Exit codes
----------
0 PASS
1 FAIL (gate violated)
2 ERROR (unexpected failure)
"""

from __future__ import annotations

import argparse
import sys

import duckdb

from src.core.audit_engine import AuditEngine


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="verify_inputs", description="Pre-audit input gates for SENTINEL-ALPHA")
    p.add_argument("--db", "--db-path", dest="db_path", default="data/sentinel_alpha.db", help="Path to DuckDB db")
    p.add_argument("--universe-id", default="ALL", help="Universe id to validate (default: ALL)")
    p.add_argument("--sample-limit", type=int, default=20, help="Sample size for failure diagnostics")
    p.add_argument(
        "--fail-on-missing-price-series",
        action="store_true",
        default=True,
        help="Fail if any eligible signal references a ticker with no price series (default: true)",
    )
    p.add_argument(
        "--no-fail-on-missing-price-series",
        dest="fail_on_missing_price_series",
        action="store_false",
        help="Do not fail on missing price series; warn-only",
    )
    p.add_argument(
        "--max-right-censored-pct",
        type=float,
        default=-1.0,
        help="If >= 0, fail when right-censored eligible signals exceed this percentage (0-100). Default: disabled",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])

    try:
        con = duckdb.connect(database=args.db_path)
        eng = AuditEngine(con=con)
        cov = eng.verify_signal_price_coverage(universe_id=args.universe_id, sample_limit=args.sample_limit)

        missing = int(cov.get("signals_missing_price_series", 0) or 0)
        eligible_total = int(cov.get("eligible_signals", 0) or 0)
        right_censored = int(cov.get("signals_right_censored", 0) or 0)
        # "Enterable" means there exists a trading session strictly after the signal date
        # (consistent with the audit engine's timing contract preconditions).
        eligible_enterable = max(0, eligible_total - right_censored)
        rc_pct = float(cov.get("pct_right_censored_signals", 0.0) or 0.0) * 100.0

        failures: list[str] = []

        if args.fail_on_missing_price_series and missing > 0:
            failures.append(
                f"eligible signals missing price series: {missing} (tickers: {cov.get('tickers_missing_price_series')})"
            )

        if args.max_right_censored_pct is not None and float(args.max_right_censored_pct) >= 0.0:
            if eligible_total > 0 and rc_pct > float(args.max_right_censored_pct):
                failures.append(
                    f"right-censored eligible signals: {rc_pct:.2f}% > {float(args.max_right_censored_pct):.2f}%"
                )

        if failures:
            print("[FAIL] verify_inputs")
            for f in failures:
                print(f"  - {f}")
            sample = cov.get("missing_price_series_sample") or []
            if sample:
                print("  - sample missing tickers:")
                for r in sample[: min(len(sample), args.sample_limit)]:
                    print(f"      {r.get('ticker')} (signals={r.get('signals')})")
            raise SystemExit(1)

        print("[PASS] verify_inputs")
        # Always show a compact summary for operator awareness.
        norm_changed = int(cov.get("signals_normalization_changed", 0) or 0)
        mapped_applied = int(cov.get("signals_mapping_applied", 0) or 0)
        print(
            f"  eligible_signals={eligible_enterable}; "
            f"eligible_signals_total={eligible_total}; "
            f"missing_price_series_signals={missing}; "
            f"right_censored_signals={right_censored}; "
            f"normalized_signals={norm_changed}; "
            f"mapped_signals={mapped_applied}"
        )
        raise SystemExit(0)

    except SystemExit:
        raise
    except Exception as e:
        print("[ERROR] verify_inputs:", str(e))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
