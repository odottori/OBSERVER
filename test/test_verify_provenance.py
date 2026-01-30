import tempfile
from datetime import date, datetime, timezone

import duckdb
import pytest

from src.db.migrate import ensure_schema, seed_default_universes
from src.tools import verify_provenance


def _new_db_path(tmpdir: str) -> str:
    return tmpdir + "/prov_gate.duckdb"


def _insert_recs_row(
    con: duckdb.DuckDBPyConnection,
    *,
    signal_date: date = date(2026, 1, 12),
    ticker: str = "AAA",
    firm: str = "NEWS-ALPHA",
    rating: str = "BUY",
    sentiment_score: float = 0.1,
    headline: str = "Test headline",
    source_url: str = "https://reuters.com/article/aaa",
    universe_id: str = "ALL",
    published_at: datetime | None = datetime(2026, 1, 12, 10, 0, tzinfo=timezone.utc),
) -> None:
    con.execute(
        """
        INSERT INTO recs(date, ticker, firm, rating, sentiment_score, headline, source_url, universe_id, published_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [signal_date, ticker, firm, rating, sentiment_score, headline, source_url, universe_id, published_at],
    )


def test_verify_provenance_passes_on_valid_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            seed_default_universes(con)
            _insert_recs_row(con)
            with pytest.raises(SystemExit) as ei:
                verify_provenance.main(["--db", db_path, "--universe-id", "ALL"])
            assert int(ei.value.code) == 0
        finally:
            con.close()


def test_verify_provenance_fails_on_missing_fields() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            seed_default_universes(con)
            # Missing published_at
            _insert_recs_row(con, published_at=None)
            with pytest.raises(SystemExit) as ei:
                verify_provenance.main(["--db", db_path])
            assert int(ei.value.code) == 1
        finally:
            con.close()


def test_verify_provenance_fails_on_placeholder_domain() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            seed_default_universes(con)
            _insert_recs_row(con, source_url="https://example.com/a")
            with pytest.raises(SystemExit) as ei:
                verify_provenance.main(["--db", db_path])
            assert int(ei.value.code) == 1
        finally:
            con.close()


def test_verify_provenance_allows_placeholder_with_flag() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = _new_db_path(td)
        con = duckdb.connect(db_path)
        try:
            ensure_schema(con)
            seed_default_universes(con)
            _insert_recs_row(con, source_url="https://example.com/a")
            with pytest.raises(SystemExit) as ei:
                verify_provenance.main(["--db", db_path, "--allow-placeholder-domains"])
            assert int(ei.value.code) == 0
        finally:
            con.close()
