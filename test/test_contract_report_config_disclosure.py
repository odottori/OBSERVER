import json

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema
from src.intelligence_engine import IntelligenceEngine


def test_report_discloses_config_json_from_audit_runs(tmp_path) -> None:
    db_path = tmp_path / "contract_report_config.duckdb"

    # Create schema + seed an audit_runs row with config_json.
    con = duckdb.connect(str(db_path))
    try:
        ensure_schema(con)

        rid = "RUN_CONFIG_DISCLOSURE_TEST"
        code_fp = ("0123456789abcdef" * 4)  # 64 hex chars

        cfg = {
            "SENTINEL_PRICE_PROVIDER_ORDER": "ALPHAVANTAGE,YFINANCE",
            "SENTINEL_DISABLE_YFINANCE": "1",
            "SENTINEL_ALLOW_ONLINE_BACKFILL": "0",
        }

        con.execute(
            """
            INSERT INTO audit_runs (run_id, status, code_fingerprint, config_json)
            VALUES (?, ?, ?, ?)
            """,
            [rid, "SUCCESS", code_fp, json.dumps(cfg)],
        )
    finally:
        con.close()

    engine = IntelligenceEngine(db_path=str(db_path))
    try:
        out_path = tmp_path / "AUDIT_COMPLETE_TEST.md"

        # Minimal frames: config disclosure should not depend on trade content.
        trades_df = pd.DataFrame()
        equity_df = pd.DataFrame()

        engine.save_master_report(trades_df=trades_df, equity_df=equity_df, path=str(out_path), run_id=rid)

        txt = out_path.read_text(encoding="utf-8")

        assert f"- run_id: `{rid}`" in txt
        assert f"code_fingerprint: `{code_fp}`" in txt

        assert "## Run Configuration (from audit_runs.config_json)" in txt
        assert "- SENTINEL_PRICE_PROVIDER_ORDER: `ALPHAVANTAGE,YFINANCE`" in txt
        assert "- SENTINEL_DISABLE_YFINANCE: `1`" in txt
        assert "- SENTINEL_ALLOW_ONLINE_BACKFILL: `0`" in txt
    finally:
        engine.close()
