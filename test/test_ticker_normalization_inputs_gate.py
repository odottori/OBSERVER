import duckdb

from src.phase0.db.migrate import ensure_schema
from src.phase0.core.audit_engine import AuditEngine


def test_verify_inputs_normalizes_single_suffix_dash_to_dot():
    """Retail providers often use dash notation for class shares (e.g. BRK-B).

    The pre-audit inputs gate must treat BRK-B as BRK.B without requiring an explicit
    ticker_mappings row, otherwise the audit may silently drop eligible signals.
    """
    con = duckdb.connect(":memory:")
    ensure_schema(con)

    # Universe membership uses canonical dot notation
    con.execute("INSERT INTO universes VALUES ('ALL','ALL','US','')")
    con.execute(
        """
        INSERT INTO universe_membership(universe_id,ticker,start_date,end_date,source,notes)
        VALUES ('ALL','BRK.B',DATE '2026-01-01',NULL,'test','')
        """
    )

    # Prices are stored under canonical dot notation
    con.execute("INSERT INTO prices(date,ticker,price,open_price) VALUES (DATE '2026-01-02','BRK.B',100.0,100.0)")

    # Signal arrives in dash notation
    con.execute(
        """
        INSERT INTO recs(date,ticker,firm,rating,sentiment_score,headline,source_url,universe_id,published_at)
        VALUES (DATE '2026-01-01','BRK-B','TEST','BUY',0.9,'','', 'ALL', TIMESTAMP '2026-01-01 00:00:00')
        """
    )

    eng = AuditEngine(con=con)
    cov = eng.verify_signal_price_coverage(universe_id="ALL", sample_limit=10)

    assert int(cov.get("eligible_signals", 0)) == 1
    assert int(cov.get("signals_missing_price_series", 0)) == 0
    assert int(cov.get("signals_right_censored", 0)) == 0

    # We expect the normalization counter to reflect the dash->dot conversion.
    assert int(cov.get("signals_normalization_changed", 0)) == 1
    # No ticker_mappings row was needed.
    assert int(cov.get("signals_mapping_applied", 0)) == 0
