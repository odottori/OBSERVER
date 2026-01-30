import duckdb
import pandas as pd

from src.db.migrate import ensure_schema
from src.core.audit_engine import AuditEngine, BacktestConfig


def _seed_universe(con: duckdb.DuckDBPyConnection, uid: str = "ALL", ticker: str = "AAPL") -> None:
    con.execute("INSERT INTO universes VALUES (?, ?, ?, ?)", [uid, uid, "US", ""])
    con.execute(
        """
        INSERT INTO universe_membership(universe_id,ticker,start_date,end_date,source,notes)
        VALUES (?, ?, DATE '2020-01-01', NULL, 'test', '')
        """,
        [uid, ticker],
    )


def test_sell_date_falls_back_to_last_available_price_date():
    """If the forward window is too short, we must still close the trade at the last known date."""

    con = duckdb.connect(":memory:")
    ensure_schema(con)
    _seed_universe(con, "ALL", "AAPL")

    # Only a handful of prices after entry (insufficient for long holding period)
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-12','AAPL',100.0,100.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-13','AAPL',101.0,101.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-14','AAPL',102.0,102.0)")

    # Signal before first price, so buy_date becomes 2026-01-12
    con.execute(
        """
        INSERT INTO recs(date,ticker,firm,rating,universe_id)
        VALUES (DATE '2026-01-10','AAPL','GS','Upgrade','ALL')
        """
    )

    eng = AuditEngine(con=con)
    cfg = BacktestConfig(holding_period_sessions=22, include_costs=False, include_taxes=False)
    df = eng.run_trade_audit("ALL", cfg)

    assert len(df) == 1
    assert str(pd.to_datetime(df.loc[0, "buy_date"]).date()) == "2026-01-12"
    # fallback to the last available price date
    assert str(pd.to_datetime(df.loc[0, "sell_date"]).date()) == "2026-01-14"
    assert bool(df.loc[0, "exit_is_fallback"]) is True
    assert df.loc[0, "exit_reason"] == "MARK_TO_MARKET_END_OF_DATA"


def test_dedup_keeps_single_trade_per_ticker_per_entry_date():
    con = duckdb.connect(":memory:")
    ensure_schema(con)
    _seed_universe(con, "ALL", "AAPL")

    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-12','AAPL',100.0,100.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-13','AAPL',101.0,101.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-02-13','AAPL',110.0,110.0)")

    # Two firms same signal day for same ticker -> must deduplicate.
    con.execute(
        "INSERT INTO recs(date,ticker,firm,rating,universe_id) VALUES (DATE '2026-01-10','AAPL','GS','Upgrade','ALL')"
    )
    con.execute(
        "INSERT INTO recs(date,ticker,firm,rating,universe_id) VALUES (DATE '2026-01-10','AAPL','UBS','Hold','ALL')"
    )

    eng = AuditEngine(con=con)
    cfg = BacktestConfig(holding_period_sessions=1, include_costs=False, include_taxes=False)
    df = eng.run_trade_audit("ALL", cfg)

    assert len(df) == 1
    assert df.loc[0, "firm"] == "GS"  # higher rating score wins
