from __future__ import annotations

from datetime import datetime, timezone

import duckdb

from src.db.migrate import ensure_schema
from src.monitoring.tca_report import build_tca_report_text


def test_tca_report_deterministic_and_alert():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    con.execute(
        """
        INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
        VALUES
          (DATE '2026-01-01', 'AAA', 100.0, 100.0, 'test', TIMESTAMP '2026-01-01 00:00:00'),
          (DATE '2026-01-02', 'AAA', 110.0, 110.0, 'test', TIMESTAMP '2026-01-02 00:00:00')
        """
    )

    con.execute(
        """
        INSERT INTO execution_orders(order_id, run_id, created_at, ticker, side, quantity, order_type, limit_price, status, notes)
        VALUES ('O1', 'R1', TIMESTAMPTZ '2026-01-01 10:00:00+00', 'AAA', 'BUY', 1.0, 'MARKET', NULL, 'FILLED', 'paper')
        """
    )

    con.execute(
        """
        INSERT INTO execution_fills(fill_id, order_id, run_id, filled_at, ticker, side, quantity, fill_price, fees, notes)
        VALUES ('F1', 'O1', 'R1', TIMESTAMPTZ '2026-01-01 10:00:00+00', 'AAA', 'BUY', 1.0, 105.0, 1.05, 'paper')
        """
    )

    txt = build_tca_report_text(con, run_id="R1", threshold_cost_drag_bp=1.0)
    assert "TCA_REPORT run_id=R1" in txt
    assert "n_orders=1 n_fills=1" in txt
    assert "ALERT" in txt
