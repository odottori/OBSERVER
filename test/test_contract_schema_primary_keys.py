import os
import tempfile
from datetime import date

import duckdb
import pytest

from src.db.migrate import ensure_schema


def _new_db_path(tmpdir: str) -> str:
    return os.path.join(tmpdir, "contract_pk.duckdb")


def test_audit_equity_primary_key_enforced() -> None:
    """Lock the contract that audit_equity is uniquely keyed by (run_id,date)."""
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "r_pk"

            con.execute(
                "INSERT INTO audit_equity VALUES (?,?,?,?,?,?,?,?,?)",
                [rid, date(2026, 1, 1), 100.0, 100.0, 0.0, 0, 0.0, 0, 0],
            )

            with pytest.raises(Exception) as ei:
                con.execute(
                    "INSERT INTO audit_equity VALUES (?,?,?,?,?,?,?,?,?)",
                    [rid, date(2026, 1, 1), 101.0, 101.0, 0.0, 0, 0.0, 0, 0],
                )

            # DuckDB error text is stable enough to check the intent.
            assert "primary key" in str(ei.value).lower() or "duplicate key" in str(ei.value).lower()
        finally:
            con.close()


def test_audit_trades_primary_key_enforced() -> None:
    """Lock the contract that trade_id is a primary key."""
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            con.execute(
                """
                INSERT INTO audit_trades(
                  trade_id, run_id, signal_date, buy_date, sell_date,
                  exit_reason, exit_is_fallback,
                  ticker, ticker_original, firm, rating, market, sector, instrument_type,
                  mom_status, risk_vol, is_tobin_tax, ftt_pct, sentiment_score,
                  exec_shift_sessions, exit_shift_sessions, halt_reason,
                  buy_price, sell_price, gross_return_pct, cost_pct, net_return_pct, trade_score, universe_id
                ) VALUES (
                  't_pk', 'r1', DATE '2026-01-01', DATE '2026-01-02', DATE '2026-01-03',
                  'NORMAL', FALSE,
                  'AAA', 'AAA', 'FIRM', 'BUY', 'US', 'TECH', 'EQUITY',
                  'OK', 0.2, FALSE, 0.0, 0.0,
                  0, 0, NULL,
                  10.0, 11.0, 0.10, 0.01, 0.09, 0.0, 'ALL'
                )
                """
            )

            with pytest.raises(Exception) as ei:
                con.execute(
                    """
                    INSERT INTO audit_trades(
                      trade_id, run_id, signal_date, buy_date, sell_date,
                      exit_reason, exit_is_fallback,
                      ticker, ticker_original, firm, rating, market, sector, instrument_type,
                      mom_status, risk_vol, is_tobin_tax, ftt_pct, sentiment_score,
                      exec_shift_sessions, exit_shift_sessions, halt_reason,
                      buy_price, sell_price, gross_return_pct, cost_pct, net_return_pct, trade_score, universe_id
                    ) VALUES (
                      't_pk', 'r2', DATE '2026-01-01', DATE '2026-01-02', DATE '2026-01-03',
                      'NORMAL', FALSE,
                      'AAA', 'AAA', 'FIRM', 'BUY', 'US', 'TECH', 'EQUITY',
                      'OK', 0.2, FALSE, 0.0, 0.0,
                      0, 0, NULL,
                      10.0, 11.0, 0.10, 0.01, 0.09, 0.0, 'ALL'
                    )
                    """
                )
            assert "primary key" in str(ei.value).lower() or "duplicate key" in str(ei.value).lower()
        finally:
            con.close()
