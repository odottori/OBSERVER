from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema
from src.phase0.db.audit_store import start_audit_run, finish_audit_run, persist_trades, persist_equity, backfill_summary


def test_audit_tables_and_persistence_roundtrip():
    con = duckdb.connect(database=':memory:')
    ensure_schema(con)

    tables = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    assert 'audit_runs' in tables
    assert 'audit_trades' in tables
    assert 'audit_equity' in tables

    run_id = 'TEST_RUN_001'
    start_audit_run(con, run_id=run_id, universe_id='ALL', holding_period_sessions=22, cfg_obj={'x': 1}, notes='unit test')

    trades = pd.DataFrame(
        {
            'signal_date': [date(2026, 1, 1)],
            'buy_date': [date(2026, 1, 2)],
            'sell_date': [date(2026, 1, 31)],
            'ticker': ['AAPL'],
            'firm': ['X'],
            'rating': ['BUY'],
            'exit_reason': ['NORMAL'],
            'exit_is_fallback': [False],
            'gross_return_pct': [10.0],
            'cost_pct': [0.75],
            'net_return_pct': [9.25],
            'trade_score': [1.0],
            'universe_id': ['ALL'],
        }
    )
    n_t = persist_trades(con, run_id, trades)
    assert n_t == 1

    equity = pd.DataFrame(
        {
            'date': [date(2026, 1, 2), date(2026, 1, 31)],
            'equity': [100000.0, 109250.0],
            'cash': [80000.0, 90000.0],
            'invested': [20000.0, 19250.0],
            'positions': [1, 0],
            'tax_paid': [0.0, 0.0],
            'executed_trades': [1, 1],
            'closed_trades': [0, 1],
        }
    )
    n_e = persist_equity(con, run_id, equity)
    assert n_e == 2

    finish_audit_run(con, run_id, status='SUCCESS')

    # Round-trip checks
    assert con.execute('SELECT COUNT(*) FROM audit_runs WHERE run_id=?', [run_id]).fetchone()[0] == 1
    assert con.execute('SELECT COUNT(*) FROM audit_trades WHERE run_id=?', [run_id]).fetchone()[0] == 1
    assert con.execute('SELECT COUNT(*) FROM audit_equity WHERE run_id=?', [run_id]).fetchone()[0] == 2

    # Summary should be empty (no gaps recorded), but must not error
    df = backfill_summary(con, run_id)
    assert isinstance(df, pd.DataFrame)
