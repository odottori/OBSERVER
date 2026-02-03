from datetime import date

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema
from src.phase0.core.audit_engine import AuditEngine, BacktestConfig


def test_entry_is_strictly_after_signal_date_weekend():
    con = duckdb.connect(database=':memory:')
    ensure_schema(con)

    # Universe membership
    con.execute("INSERT INTO universes VALUES ('ALL','All','MULTI','')")
    con.execute(
        "INSERT INTO universe_membership(universe_id,ticker,start_date,end_date,source,notes) VALUES ('ALL','AAPL',DATE '2020-01-01',NULL,'test','')"
    )

    # Prices only on trading days (Fri + Mon)
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-09','AAPL',100.0,100.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-12','AAPL',101.0,101.0)")
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-02-11','AAPL',110.0,110.0)")

    # Signal on Saturday
    con.execute(
        "INSERT INTO recs(date,ticker,firm,rating,sentiment_score,headline,source_url,universe_id,published_at) VALUES (DATE '2026-01-10','AAPL','GS','Buy',NULL,NULL,NULL,'ALL',NULL)"
    )

    eng = AuditEngine(con=con)
    cfg = BacktestConfig(holding_period_sessions=1, include_costs=False, include_taxes=False)
    trades = eng.run_trade_audit(universe_id='ALL', cfg=cfg)

    assert len(trades) == 1

    buy_date = pd.to_datetime(trades.iloc[0]['buy_date']).date()
    signal_date = pd.to_datetime(trades.iloc[0]['signal_date']).date()

    assert str(buy_date) == '2026-01-12'
    assert str(signal_date) == '2026-01-10'
    assert buy_date > signal_date
