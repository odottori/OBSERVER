import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema
from src.phase0.core.audit_engine import AuditEngine, BacktestConfig


def test_portfolio_simulation_marks_to_market_and_enforces_one_position_per_ticker():
    con = duckdb.connect(":memory:")
    ensure_schema(con)

    # Universe
    con.execute("INSERT INTO universes VALUES ('ALL','ALL','US','')")
    con.execute(
        """
        INSERT INTO universe_membership(universe_id,ticker,start_date,end_date,source,notes)
        VALUES ('ALL','AAPL',DATE '2020-01-01',NULL,'test','')
        """
    )

    # Prices across four sessions
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-12','AAPL',100.0,100.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-13','AAPL',90.0,90.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-14','AAPL',95.0,95.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-15','AAPL',110.0,110.0)")

    eng = AuditEngine(con=con)

    # Two overlapping trades on the same ticker; second starts before first exits.
    trades = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "firm": "GS",
                "buy_date": pd.Timestamp("2026-01-12"),
                "sell_date": pd.Timestamp("2026-01-15"),
                "buy_price": 100.0,
                "sell_price": 110.0,
                "risk_vol": 10.0,
                "trade_score": 1.0,
                "exit_is_fallback": False,
                "exit_reason": "HOLDING_PERIOD",
                "gross_return_pct": 10.0,
                "net_return_pct": 10.0,
            },
            {
                "ticker": "AAPL",
                "firm": "UBS",
                "buy_date": pd.Timestamp("2026-01-13"),
                "sell_date": pd.Timestamp("2026-01-14"),
                "buy_price": 90.0,
                "sell_price": 95.0,
                "risk_vol": 10.0,
                "trade_score": 0.5,
                "exit_is_fallback": False,
                "exit_reason": "HOLDING_PERIOD",
                "gross_return_pct": 5.5555,
                "net_return_pct": 5.5555,
            },
        ]
    )

    cfg = BacktestConfig(
        starting_capital=10000.0,
        include_costs=False,
        include_taxes=False,
        max_positions=10,
        cash_reserve_pct=0.0,
        risk_per_trade=0.5,
        max_position_pct=1.0,
    )

    equity = eng.simulate_portfolio(trades, cfg=cfg)

    # Daily calendar should be present
    assert len(equity) == 4
    assert list(pd.to_datetime(equity["date"]).dt.date.astype(str)) == [
        "2026-01-12",
        "2026-01-13",
        "2026-01-14",
        "2026-01-15",
    ]

    # Only one executed trade (second overlapped and should be skipped)
    assert int(equity["executed_trades"].iloc[-1]) == 1
    assert int(equity["closed_trades"].iloc[-1]) == 1

    # Equity should reflect mark-to-market dip on 2026-01-13 (price 90)
    assert float(equity["equity"].iloc[1]) < float(equity["equity"].iloc[0])
