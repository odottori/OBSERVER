import duckdb

from src.phase0.db.migrate import ensure_schema


def test_phase1_dataops_tables_exist_and_pk_work():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert "market_halts" in tables
    assert "ticker_halts" in tables
    assert "dq_runs" in tables
    assert "dq_findings" in tables
    assert "dq_metrics_daily" in tables

    # Composite PK on dq_metrics_daily should dedupe inserts
    con.execute(
        """
        INSERT INTO dq_metrics_daily(run_id, asof_date, market, metric, value, created_at)
        VALUES ('R1', DATE '2026-01-09', 'US', 'tickers', 3, now())
        ON CONFLICT(run_id, asof_date, market, metric) DO NOTHING
        """
    )
    con.execute(
        """
        INSERT INTO dq_metrics_daily(run_id, asof_date, market, metric, value, created_at)
        VALUES ('R1', DATE '2026-01-09', 'US', 'tickers', 3, now())
        ON CONFLICT(run_id, asof_date, market, metric) DO NOTHING
        """
    )

    assert con.execute("SELECT COUNT(*) FROM dq_metrics_daily").fetchone()[0] == 1
