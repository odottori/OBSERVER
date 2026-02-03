from __future__ import annotations

"""Main pipeline runner.

This script is intentionally simple:
1) Ensure DB schema is up to date (DuckDB migrations)
2) Optional ingestion (news / prices) via SentinelAlpha
3) Produce a deterministic audit report from the trade ledger

Run:
    Windows/PowerShell: py -3.14 main.py
    Linux/macOS:      python main.py
"""

import os
from uuid import uuid4

from src.phase0.db.migrate import cli_migrate
from src.sentinel_alpha import SentinelAlpha
from src.intelligence_engine import IntelligenceEngine


def main() -> None:
    print("SENTINEL-ALPHA: pipeline start")

    # --- Certification defaults (override via env vars) ---
    # Online backfill (multi-source) is enabled by default for the full pipeline.
    os.environ.setdefault("SENTINEL_ALLOW_ONLINE_BACKFILL", "1")
    os.environ.setdefault("SENTINEL_BACKFILL_WINDOW_DAYS", "90")

    # A7.0: disclosure defaults for retail-realism roadmap.
    os.environ.setdefault("SENTINEL_DIVIDEND_POLICY", "B")
    os.environ.setdefault("SENTINEL_TIMING_MODE", "T_PLUS_1")

    # Provider order is controllable. In some environments yfinance is blocked;
    # for this reason we default to stooq-only unless you explicitly opt-in.
    os.environ.setdefault("SENTINEL_DISABLE_YFINANCE", "1")
    os.environ.setdefault("SENTINEL_PRICE_PROVIDER_ORDER", "stooq")

    # Stable run_id for certification and DB persistence.
    os.environ.setdefault("SENTINEL_RUN_ID", uuid4().hex)

    # IMPORTANT: allow the runner/setup to override the DB path via env var.
    # Default remains the canonical local DB.
    db_path = os.environ.get("SENTINEL_ALPHA_DB_PATH", os.path.join("data", "sentinel_alpha.db"))
    cli_migrate(db_path)

    # Optional ingestion (kept, but not required for auditing an existing DB)
    sentinel = SentinelAlpha(db_path=db_path)
    try:
        # If your environment does not allow external providers, comment these out.
        # sentinel.update_news(universe_id="ALL")
        # sentinel.update_prices(universe_id="ALL")
        pass
    finally:
        sentinel.close()

    engine = IntelligenceEngine(db_path=db_path)
    try:
        run_id, report_path, _, _ = engine.certify_run(
            universe_id="ALL",
            holding_period_sessions=22,
            notes="main.py run",
        )
        print(f"[+] Audit report written: {report_path}")
        print(f"[+] run_id: {run_id}")
    finally:
        engine.close()


if __name__ == "__main__":
    main()
