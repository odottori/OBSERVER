import os
import tempfile
from datetime import date, datetime, timezone

import duckdb
import pytest

from src.phase0.db.migrate import ensure_schema
from src.phase0.tools import verify_run


def _new_db_path(tmpdir: str) -> str:
    # DuckDB refuses to open an *existing* empty file. Create a path that does
    # not exist yet.
    return os.path.join(tmpdir, "contract_verify.duckdb")


def _seed_minimal_pass_case(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    """Insert the minimal rows needed for verify_run to PASS."""
    # audit_equity: at least one row, end positions must be 0
    con.execute(
        """
        INSERT INTO audit_equity(run_id, date, equity, cash, invested, positions, tax_paid, executed_trades, closed_trades)
        VALUES (?, ?, 100000.0, 100000.0, 0.0, 0, 0.0, 0, 0)
        """,
        [run_id, date(2026, 1, 1)],
    )

    # audit_trades: no NULL dates, market/universe_id populated
    con.execute(
        """
        INSERT INTO audit_trades(
          trade_id, run_id, signal_date, buy_date, sell_date, exit_reason, exit_is_fallback,
          ticker, ticker_original, firm, rating, market, sector, instrument_type,
          mom_status, risk_vol, is_tobin_tax, ftt_pct, sentiment_score,
          exec_shift_sessions, exit_shift_sessions, halt_reason,
          buy_price, sell_price, gross_return_pct, cost_pct, net_return_pct, trade_score, universe_id
        )
        VALUES (
          't1', ?, ?, ?, ?, 'NORMAL', FALSE,
          'AAA', 'AAA', 'FIRM', 'BUY', 'US', 'TECH', 'EQUITY',
          'OK', 0.2, FALSE, 0.0, 0.0,
          0, 0, NULL,
          10.0, 11.0, 0.10, 0.01, 0.09, 0.0, 'ALL'
        )
        """,
        [run_id, date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 2)],
    )


def test_verify_run_passes_minimal_seed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "rid_pass"
            _seed_minimal_pass_case(con, rid)

            # Should not raise.
            verify_run.main(["--db", db_path, "--run-id", rid])
        finally:
            con.close()


def test_verify_run_fails_if_fallback_exits_without_data_gaps() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "rid_fallback"
            _seed_minimal_pass_case(con, rid)

            # Flip the trade to a fallback exit. No data_gaps rows are inserted.
            con.execute(
                "UPDATE audit_trades SET exit_reason='FALLBACK_LAST_PRICE', exit_is_fallback=TRUE WHERE run_id = ?",
                [rid],
            )

            with pytest.raises(SystemExit) as ei:
                verify_run.main(["--db", db_path, "--run-id", rid])
            assert int(ei.value.code) == 1
        finally:
            con.close()


def test_verify_run_passes_if_fallback_exits_have_data_gaps_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "rid_fallback_ok"
            _seed_minimal_pass_case(con, rid)

            con.execute(
                "UPDATE audit_trades SET exit_reason='FALLBACK_LAST_PRICE', exit_is_fallback=TRUE WHERE run_id = ?",
                [rid],
            )
            # Minimal audit trail: only run_id is required; other columns are nullable.
            con.execute(
                "INSERT INTO data_gaps(run_id, kind, ticker, requested_at, status, provider) VALUES (?, 'prices', 'AAA', ?, 'FAILED', 'stooq')",
                [rid, datetime.now(timezone.utc)],
            )

            # Should not raise.
            verify_run.main(["--db", db_path, "--run-id", rid])
        finally:
            con.close()


def test_verify_run_fails_on_null_market_or_universe_id() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "rid_null_meta"
            _seed_minimal_pass_case(con, rid)

            con.execute("UPDATE audit_trades SET market = NULL WHERE run_id = ?", [rid])

            with pytest.raises(SystemExit) as ei:
                verify_run.main(["--db", db_path, "--run-id", rid])
            assert int(ei.value.code) == 1
        finally:
            con.close()


def test_verify_run_fails_if_end_positions_nonzero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            rid = "rid_pos"
            _seed_minimal_pass_case(con, rid)

            con.execute(
                "UPDATE audit_equity SET positions = 1 WHERE run_id = ? AND date = ?",
                [rid, date(2026, 1, 1)],
            )

            with pytest.raises(SystemExit) as ei:
                verify_run.main(["--db", db_path, "--run-id", rid])
            assert int(ei.value.code) == 1
        finally:
            con.close()
