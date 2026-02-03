import duckdb

from src.phase0.db.migrate import ensure_schema
from src.phase0.tools.verify_ticker_mappings import check_ticker_mappings


def test_verify_ticker_mappings_passes_on_non_overlapping_rows():
    con = duckdb.connect(":memory:")
    ensure_schema(con)

    con.execute(
        """
        INSERT INTO ticker_mappings(alias_ticker, canonical_ticker, start_date, end_date, source, notes)
        VALUES
          ('FB', 'META', DATE '2021-10-28', NULL, 'test', ''),
          ('META', 'META', DATE '1900-01-01', NULL, 'test', 'identity mapping allowed')
        """
    )

    rep = check_ticker_mappings(con)
    assert rep.get("failures") == []
    assert int(rep.get("n_overlaps", 0)) == 0
    assert int(rep.get("n_cycles", 0)) == 0


def test_verify_ticker_mappings_fails_on_overlaps():
    con = duckdb.connect(":memory:")
    ensure_schema(con)

    con.execute(
        """
        INSERT INTO ticker_mappings(alias_ticker, canonical_ticker, start_date, end_date, source, notes)
        VALUES
          ('A', 'B', DATE '2020-01-01', DATE '2020-12-31', 'test', ''),
          ('A', 'C', DATE '2020-06-01', DATE '2021-01-01', 'test', '')
        """
    )

    rep = check_ticker_mappings(con)
    assert rep.get("failures")
    assert int(rep.get("n_overlaps", 0)) > 0


def test_verify_ticker_mappings_fails_on_effective_cycle_with_overlap():
    con = duckdb.connect(":memory:")
    ensure_schema(con)

    # A->B valid from 2020-01-01 onward
    # B->A valid from 2020-06-01 onward
    # Their intersection is non-empty => effective cycle.
    con.execute(
        """
        INSERT INTO ticker_mappings(alias_ticker, canonical_ticker, start_date, end_date, source, notes)
        VALUES
          ('A', 'B', DATE '2020-01-01', NULL, 'test', ''),
          ('B', 'A', DATE '2020-06-01', NULL, 'test', '')
        """
    )

    rep = check_ticker_mappings(con)
    assert rep.get("failures")
    assert int(rep.get("n_cycles", 0)) > 0
