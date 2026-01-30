import duckdb
import pandas as pd

from src.db.migrate import ensure_schema
from src.core.audit_engine import AuditEngine, BacktestConfig


def _bootstrap_universe(con: duckdb.DuckDBPyConnection, ticker: str) -> None:
    """Insert minimal universe/membership/mapping rows."""
    con.execute("INSERT INTO universes VALUES ('ALL','ALL','US','')")
    con.execute(
        """
        INSERT INTO universe_membership(universe_id, ticker, start_date, end_date, source, notes)
        VALUES ('ALL', ?, '2000-01-01', '2099-12-31', 'TEST', '')
        """,
        [ticker],
    )
    con.execute(
        """
        INSERT INTO ticker_mappings(alias_ticker, canonical_ticker, start_date, end_date, source, notes)
        VALUES (?, ?, '2000-01-01', '2099-12-31', 'TEST', '')
        """,
        [ticker, ticker],
    )


def test_min_trade_notional_skips_micro_trades():
    con = duckdb.connect(database=':memory:')
    ensure_schema(con)

    ticker = 'AAA'
    _bootstrap_universe(con, ticker)

    # Price series (2 days)
    con.execute(
        """
        INSERT INTO prices(date, ticker, price, source, fetched_at)
        VALUES
          ('2026-01-12', ?, 333.33, 'TEST', NOW()),
          ('2026-01-13', ?, 333.33, 'TEST', NOW())
        """,
        [ticker, ticker],
    )

    trades = pd.DataFrame(
        [
            {
                'ticker': ticker,
                'buy_date': '2026-01-12',
                'sell_date': '2026-01-13',
                'buy_price': 333.33,
                'sell_price': 333.33,
                'risk_vol': 10.0,
                'trade_score': 1.0,
                'firm': 'TEST',
            }
        ]
    )

    engine = AuditEngine(con=con)
    cfg = BacktestConfig(
        starting_capital=1000.0,
        include_costs=False,
        include_taxes=False,
        cash_reserve_pct=0.0,
        risk_per_trade=1.0,
        max_position_pct=1.0,
        whole_shares=True,
        min_trade_notional=1500.0,
    )

    eq = engine.simulate_portfolio(trades, cfg=cfg)
    assert int(eq['executed_trades'].iloc[-1]) == 0
    assert float(eq['equity'].iloc[-1]) == 1000.0


def test_cash_dividends_credit_on_pay_date_after_exit():
    con = duckdb.connect(database=':memory:')
    ensure_schema(con)

    ticker = 'AAPL'
    _bootstrap_universe(con, ticker)

    # Price series includes pay date.
    con.execute(
        """
        INSERT INTO prices(date, ticker, price, source, fetched_at)
        VALUES
          ('2026-01-12', ?, 100.0, 'TEST', NOW()),
          ('2026-01-13', ?, 100.0, 'TEST', NOW()),
          ('2026-01-14', ?, 100.0, 'TEST', NOW()),
          ('2026-01-15', ?, 100.0, 'TEST', NOW())
        """,
        [ticker, ticker, ticker, ticker],
    )

    # Dividend: ex-date 13, pay-date 15, $1/share
    con.execute(
        """
        INSERT INTO dividends(ticker, ex_date, pay_date, amount, currency, source, fetched_at)
        VALUES (?, '2026-01-13', '2026-01-15', 1.0, 'USD', 'TEST', NOW())
        """,
        [ticker],
    )

    trades = pd.DataFrame(
        [
            {
                'ticker': ticker,
                'buy_date': '2026-01-12',
                'sell_date': '2026-01-14',
                'buy_price': 100.0,
                'sell_price': 100.0,
                'risk_vol': 10.0,
                'trade_score': 1.0,
                'firm': 'TEST',
            }
        ]
    )

    engine = AuditEngine(con=con)
    cfg = BacktestConfig(
        starting_capital=1000.0,
        include_costs=False,
        include_taxes=False,
        cash_reserve_pct=0.0,
        risk_per_trade=1.0,
        max_position_pct=1.0,
        whole_shares=True,
        min_trade_notional=0.0,
        include_dividends=True,
        dividend_withholding_rate=0.0,
    )

    eq = engine.simulate_portfolio(trades, cfg=cfg)

    # Dividend paid on pay date even if the position was closed the day before.
    last = eq.iloc[-1]
    assert str(pd.to_datetime(last['date']).date()) == '2026-01-15'
    assert float(last['equity']) == 1010.0
    assert float(last.get('dividends_paid', 0.0)) == 10.0
    assert int(last.get('dividends_events', 0)) == 1
