import os
import re
import tempfile
from datetime import datetime, timezone

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema
from src.phase0.db.audit_store import compute_code_fingerprint
from src.intelligence_engine import IntelligenceEngine


def test_report_includes_run_id_and_code_fingerprint_when_available() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "contract_report.duckdb")
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "rid_report"
            fp = compute_code_fingerprint(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            # Insert run header with fingerprint (mimics start_audit_run behavior).
            con.execute(
                "INSERT INTO audit_runs(run_id, started_at, status, code_fingerprint) VALUES (?,?,?,?)",
                [rid, datetime.now(timezone.utc), "SUCCESS", fp],
            )
        finally:
            con.close()

        # Minimal dataframes sufficient for save_master_report.
        trades_df = pd.DataFrame([])
        equity_df = pd.DataFrame(
            [
                {
                    "date": "2026-01-01",
                    "equity": 100000.0,
                    "cash": 100000.0,
                    "invested": 0.0,
                    "positions": 0,
                    "tax_paid": 0.0,
                    "executed_trades": 0,
                    "closed_trades": 0,
                }
            ]
        )

        engine = IntelligenceEngine(db_path=db_path)
        try:
            out_path = os.path.join(td, "AUDIT_COMPLETE_TEST.md")
            engine.save_master_report(trades_df=trades_df, equity_df=equity_df, path=out_path, run_id=rid)

            txt = open(out_path, "r", encoding="utf-8").read()
            assert f"- run_id: `{rid}`" in txt
            assert "code_fingerprint" in txt
            # Fingerprint must look like a SHA-256 hex digest.
            m = re.search(r"code_fingerprint: `([0-9a-f]{64})`", txt)
            assert m, "Expected code_fingerprint disclosure in report"
        finally:
            engine.close()