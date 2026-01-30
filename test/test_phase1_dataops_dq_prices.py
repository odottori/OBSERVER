from datetime import date

import duckdb

from src.db.migrate import ensure_schema
from src.dataops.dq_prices import run_price_data_quality


def _seed_metadata(con):
    con.execute(
        """
        INSERT INTO metadata(ticker, market) VALUES
        ('AAPL', 'US'),
        ('MSFT', 'US'),
        ('TSLA', 'US')
        ON CONFLICT(ticker) DO NOTHING
        """
    )


def _seed_prices(con):
    # Business days in window: 2026-01-05..2026-01-09 (Mon..Fri)
    # Market halt on 2026-01-07 should be excluded from expected sessions.
    con.execute(
        """
        INSERT INTO market_halts(market, start_date, end_date, reason, source)
        VALUES ('US', DATE '2026-01-07', DATE '2026-01-07', 'TEST_HALT', 'TEST')
        ON CONFLICT(market, start_date) DO NOTHING
        """
    )

    # AAPL: complete coverage on non-halt sessions (no findings expected)
    for d in ("2026-01-05", "2026-01-06", "2026-01-08", "2026-01-09"):
        con.execute(
            """
            INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
            VALUES (CAST(? AS DATE), 'AAPL', 100.0, 99.0, 'TEST', now())
            ON CONFLICT(date, ticker) DO NOTHING
            """,
            [d],
        )

    # MSFT: missing 2026-01-08 (should generate PRICE_MISSING)
    # Also: one invalid row (price <= 0) -> should be counted in invalid_rows metric
    con.execute(
        """
        INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
        VALUES (DATE '2026-01-05', 'MSFT', 0.0, 200.0, 'TEST', now())
        ON CONFLICT(date, ticker) DO NOTHING
        """
    )
    for d in ("2026-01-06", "2026-01-09"):
        con.execute(
            """
            INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
            VALUES (CAST(? AS DATE), 'MSFT', 200.0, 199.0, 'TEST', now())
            ON CONFLICT(date, ticker) DO NOTHING
            """,
            [d],
        )

    # TSLA: stale after 2026-01-06 (should generate PRICE_STALE for 2026-01-08..2026-01-09)
    for d in ("2026-01-05", "2026-01-06"):
        con.execute(
            """
            INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
            VALUES (CAST(? AS DATE), 'TSLA', 300.0, 299.0, 'TEST', now())
            ON CONFLICT(date, ticker) DO NOTHING
            """,
            [d],
        )


def test_phase1_dq_prices_halt_aware_missing_stale_invalid_and_idempotent():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    _seed_metadata(con)
    _seed_prices(con)

    res1 = run_price_data_quality(
        con,
        run_id="DQTEST",
        asof_date="2026-01-09",
        window_days=5,
    )
    assert res1.status == "SUCCESS"

    # Should persist a single run row
    assert con.execute("SELECT COUNT(*) FROM dq_runs WHERE run_id='DQTEST'").fetchone()[0] == 1

    # Expected findings:
    # - MSFT missing 2026-01-08
    # - TSLA stale 2026-01-08..2026-01-09
    findings = con.execute(
        """
        SELECT kind, ticker, start_date, end_date, count
        FROM dq_findings
        WHERE run_id='DQTEST'
        ORDER BY kind, ticker, start_date
        """
    ).fetchall()

    assert ("PRICE_MISSING", "MSFT", date(2026, 1, 8), date(2026, 1, 8), 1) in findings
    assert ("PRICE_MISSING", "TSLA", date(2026, 1, 8), date(2026, 1, 9), 2) in findings
    assert ("PRICE_STALE", "TSLA", date(2026, 1, 8), date(2026, 1, 9), 2) in findings

    # DqResult should count invalid rows (MSFT price=0.0 on 2026-01-05)
    assert res1.invalid_rows == 1

    # Metrics sanity (ALL)
    m_all = dict(
        con.execute(
            """
            SELECT metric, value
            FROM dq_metrics_daily
            WHERE run_id='DQTEST' AND market='ALL'
            """
        ).fetchall()
    )

    assert int(m_all["tickers"]) == 3
    assert int(m_all["missing_tickers"]) == 2
    assert int(m_all["stale_tickers"]) == 1
    assert int(m_all["invalid_rows"]) == 1
    assert int(m_all["findings"]) == len(findings)

    # Per-market rollups exist (US tickers)
    m_us = dict(
        con.execute(
            """
            SELECT metric, value
            FROM dq_metrics_daily
            WHERE run_id='DQTEST' AND market='US'
            """
        ).fetchall()
    )
    assert int(m_us["tickers"]) == 3

    # Run again with same run_id: should remain idempotent (no duplicates)
    res2 = run_price_data_quality(
        con,
        run_id="DQTEST",
        asof_date="2026-01-09",
        window_days=5,
    )
    assert res2.status == "SUCCESS"
    assert con.execute("SELECT COUNT(*) FROM dq_runs WHERE run_id='DQTEST'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM dq_findings WHERE run_id='DQTEST'").fetchone()[0] == len(findings)
