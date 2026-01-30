import pytest
import duckdb
import pandas as pd
from datetime import datetime

from src.sentinel_alpha import SentinelAlpha
from src.db.migrate import ensure_schema
from src.core.audit_engine import AuditEngine, BacktestConfig


class MockSentinel(SentinelAlpha):
    """SentinelAlpha con DB in-memory per test."""

    def __init__(self):
        super().__init__(db_path=":memory:")


@pytest.fixture
def engine():
    return MockSentinel()


def test_db_init(engine: MockSentinel):
    tables = engine.con.execute("SHOW TABLES").df()
    assert "recs" in set(tables["name"].tolist())
    assert "prices" in set(tables["name"].tolist())


def test_duplicate_recs(engine: MockSentinel):
    d = datetime(2026, 1, 10).date()

    # recs has a richer schema; specify columns explicitly.
    for _ in range(3):
        engine.con.execute(
            """
            INSERT INTO recs(date, ticker, firm, rating, universe_id)
            VALUES (?, 'AAPL', 'UBS', 'Buy', 'ALL')
            ON CONFLICT(date, ticker, firm) DO NOTHING
            """,
            [d],
        )

    count = engine.con.execute("SELECT COUNT(*) FROM recs").fetchone()[0]
    assert count == 1


def test_weekend_time_alignment_is_conservative_next_session():
    """Signal on weekend must enter on first trading session AFTER the signal date."""

    con = duckdb.connect(":memory:")
    ensure_schema(con)

    # Universe membership
    con.execute("INSERT INTO universes VALUES ('ALL','All','MULTI','')")
    con.execute(
        """
        INSERT INTO universe_membership(universe_id, ticker, start_date, end_date, source, notes)
        VALUES ('ALL','AAPL', DATE '2020-01-01', NULL, 'test', '')
        """
    )

    # Prices: Friday + Monday
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-09','AAPL',100.0,100.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-12','AAPL',101.0,101.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-13','AAPL',102.0,102.0)")

    # Signal on Saturday
    con.execute(
        """
        INSERT INTO recs(date,ticker,firm,rating,universe_id)
        VALUES (DATE '2026-01-10','AAPL','GS','Buy','ALL')
        """
    )

    eng = AuditEngine(con=con)
    cfg = BacktestConfig(holding_period_sessions=1, include_costs=False, include_taxes=False)
    trades = eng.run_trade_audit(universe_id="ALL", cfg=cfg)

    assert len(trades) == 1
    buy_date = pd.to_datetime(trades.iloc[0]["buy_date"]).date()
    signal_date = pd.to_datetime(trades.iloc[0]["signal_date"]).date()

    assert str(signal_date) == "2026-01-10"
    assert str(buy_date) == "2026-01-12"  # Monday
    assert buy_date > signal_date
