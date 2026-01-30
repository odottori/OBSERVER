from __future__ import annotations

from datetime import datetime, timezone, date

import duckdb

from src.db.migrate import ensure_schema
from src.execution.paper_broker import execute_paper_broker


def test_execute_paper_broker_writes_orders_and_fills():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    d = date(2026, 1, 1)

    con.execute(
        """
        INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
        VALUES (?, 'AAPL', 100.0, 100.0, 'test', ?)
        """,
        [d, datetime.now(timezone.utc)],
    )

    con.execute(
        """
        INSERT INTO momentum_rankings(date, ticker, m_ret, rnk, signal)
        VALUES (?, 'AAPL', 0.10, 1, 'BUY')
        """,
        [d],
    )

    res = execute_paper_broker(con, run_id="TEST_RUN", asof_date=d, top_n=1)
    assert res.orders_written == 1
    assert res.fills_written == 1

    assert con.execute("SELECT COUNT(*) FROM execution_orders").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM execution_fills").fetchone()[0] == 1


def test_execute_paper_broker_rejects_when_cash_too_low():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    d = date(2026, 1, 1)

    con.execute(
        """
        INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
        VALUES (?, 'AAPL', 100.0, 100.0, 'test', ?)
        """,
        [d, datetime.now(timezone.utc)],
    )
    con.execute(
        """
        INSERT INTO momentum_rankings(date, ticker, m_ret, rnk, signal)
        VALUES (?, 'AAPL', 0.10, 1, 'BUY')
        """,
        [d],
    )

    res = execute_paper_broker(con, run_id="TEST_RUN", asof_date=d, top_n=1, starting_cash=0.0)
    assert res.orders_written == 1
    assert res.fills_written == 0

    assert con.execute("SELECT COUNT(*) FROM execution_orders WHERE status = 'REJECTED'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM execution_fills").fetchone()[0] == 0
