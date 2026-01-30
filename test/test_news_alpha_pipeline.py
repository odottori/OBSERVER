from __future__ import annotations

import sys
from pathlib import Path

import duckdb

# Ensure repo root (containing `src/`) is importable when running standalone.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.news_alpha.run import FIRM, MODEL, main as news_alpha_main  # noqa: E402


def _make_min_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE universes(universe_id VARCHAR, universe_name VARCHAR, region VARCHAR, notes VARCHAR);
            CREATE TABLE universe_membership(
                universe_id VARCHAR,
                ticker VARCHAR,
                start_date DATE,
                end_date DATE,
                source VARCHAR,
                notes VARCHAR
            );
            CREATE TABLE recs(
                date DATE,
                ticker VARCHAR,
                firm VARCHAR,
                rating VARCHAR,
                sentiment_score DOUBLE,
                headline VARCHAR,
                source_url VARCHAR,
                published_at TIMESTAMP
            );
            CREATE TABLE sentiment_cache(
                text_hash VARCHAR,
                model VARCHAR,
                sentiment_score DOUBLE,
                text VARCHAR
            );
            """
        )
        con.execute("INSERT INTO universes VALUES ('ALL','ALL','US','')")
        con.execute(
            """
            INSERT INTO universe_membership(universe_id,ticker,start_date,end_date,source,notes)
            VALUES
                ('ALL','AAPL',DATE '2020-01-01',NULL,'test',''),
                ('ALL','BRK.B',DATE '2020-01-01',NULL,'test','')
            """
        )
    finally:
        con.close()


def _make_min_db_alt_sentiment_cache(db_path: Path) -> None:
    """Create a minimal DB variant where sentiment_cache uses a non-canonical score column.

    Some repos may have `sentiment` instead of `sentiment_score`.
    """

    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE universes(universe_id VARCHAR, universe_name VARCHAR, region VARCHAR, notes VARCHAR);
            CREATE TABLE universe_membership(
                universe_id VARCHAR,
                ticker VARCHAR,
                start_date DATE,
                end_date DATE,
                source VARCHAR,
                notes VARCHAR
            );
            CREATE TABLE recs(
                date DATE,
                ticker VARCHAR,
                firm VARCHAR,
                rating VARCHAR,
                sentiment_score DOUBLE,
                headline VARCHAR,
                source_url VARCHAR,
                published_at TIMESTAMP
            );
            CREATE TABLE sentiment_cache(
                text_hash VARCHAR,
                model VARCHAR,
                sentiment DOUBLE,
                text VARCHAR
            );
            """
        )
        con.execute("INSERT INTO universes VALUES ('ALL','ALL','US','')")
        con.execute(
            """
            INSERT INTO universe_membership(universe_id,ticker,start_date,end_date,source,notes)
            VALUES
                ('ALL','AAPL',DATE '2020-01-01',NULL,'test',''),
                ('ALL','BRK.B',DATE '2020-01-01',NULL,'test','')
            """
        )
    finally:
        con.close()


def _run(db_path: Path, fixtures: Path, *, overwrite: bool = False) -> None:
    args = [
        "--db",
        str(db_path),
        "--universe-id",
        "ALL",
        "--date-from",
        "2026-01-12",
        "--date-to",
        "2026-01-13",
        "--fixtures",
        str(fixtures),
        "--log-level",
        "ERROR",
    ]
    if overwrite:
        args.append("--overwrite")
    rc = news_alpha_main(args)
    assert rc == 0


def test_log_file_parent_directory_is_created(tmp_path: Path) -> None:
    db_path = tmp_path / "t.duckdb"
    _make_min_db(db_path)

    fixtures = (Path(__file__).resolve().parent / "fixtures" / "news_alpha" / "basic.jsonl")
    assert fixtures.exists()

    log_file = tmp_path / "runs" / "news_alpha.log"
    # Intentionally do NOT create tmp_path/"runs".
    args = [
        "--db",
        str(db_path),
        "--universe-id",
        "ALL",
        "--date-from",
        "2026-01-12",
        "--date-to",
        "2026-01-13",
        "--fixtures",
        str(fixtures),
        "--log-level",
        "INFO",
        "--log-json",
        "--log-file",
        str(log_file),
    ]
    rc = news_alpha_main(args)
    assert rc == 0
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert '"event": "NEWS_ALPHA_START"' in content


def test_writes_recs_and_cache_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "t.duckdb"
    _make_min_db(db_path)

    fixtures = (Path(__file__).resolve().parent / "fixtures" / "news_alpha" / "basic.jsonl")
    assert fixtures.exists()

    _run(db_path, fixtures)

    con = duckdb.connect(str(db_path))
    try:
        recs = con.execute(
            "SELECT date, ticker, firm, rating, sentiment_score FROM recs WHERE firm = ? ORDER BY ticker",
            [FIRM],
        ).fetchall()
        assert len(recs) == 2

        # Normalization: BRK-B -> BRK.B
        assert recs[0][1] == "AAPL"
        assert recs[1][1] == "BRK.B"

        # Dedup + aggregation check:
        # AAPL has one negative (misses) and one positive (gains+upgrade) => mean 0.0 => HOLD
        aapl = [r for r in recs if r[1] == "AAPL"][0]
        assert aapl[3] == "HOLD"
        assert abs(float(aapl[4]) - 0.0) < 1e-12

        brk = [r for r in recs if r[1] == "BRK.B"][0]
        assert brk[3] == "BUY"
        assert abs(float(brk[4]) - 1.0) < 1e-12

        cache_count = con.execute(
            "SELECT COUNT(*) FROM sentiment_cache WHERE model = ?",
            [MODEL],
        ).fetchone()[0]
        assert cache_count == 5

        # Re-run without overwrite should not add duplicates.
        _run(db_path, fixtures)
        recs2 = con.execute("SELECT COUNT(*) FROM recs WHERE firm = ?", [FIRM]).fetchone()[0]
        cache2 = con.execute("SELECT COUNT(*) FROM sentiment_cache WHERE model = ?", [MODEL]).fetchone()[0]
        assert recs2 == 2
        assert cache2 == 5

        # Overwrite should delete then re-insert (still same counts).
        _run(db_path, fixtures, overwrite=True)
        recs3 = con.execute("SELECT COUNT(*) FROM recs WHERE firm = ?", [FIRM]).fetchone()[0]
        cache3 = con.execute("SELECT COUNT(*) FROM sentiment_cache WHERE model = ?", [MODEL]).fetchone()[0]
        assert recs3 == 2
        assert cache3 == 5

    finally:
        con.close()


def test_sentiment_cache_schema_variation_sentiment_column(tmp_path: Path) -> None:
    """NEWS-ALPHA must tolerate sentiment_cache schemas where the score column isn't named sentiment_score."""

    db_path = tmp_path / "t_alt.duckdb"
    _make_min_db_alt_sentiment_cache(db_path)

    fixtures = (Path(__file__).resolve().parent / "fixtures" / "news_alpha" / "basic.jsonl")
    assert fixtures.exists()

    _run(db_path, fixtures)

    con = duckdb.connect(str(db_path))
    try:
        # Cache should be written to the 'sentiment' column.
        cache_count = con.execute(
            "SELECT COUNT(*) FROM sentiment_cache WHERE model = ?",
            [MODEL],
        ).fetchone()[0]
        assert cache_count == 5
        # Sanity: values are within bounds.
        bounds = con.execute(
            "SELECT MIN(sentiment), MAX(sentiment) FROM sentiment_cache WHERE model = ?",
            [MODEL],
        ).fetchone()
        assert float(bounds[0]) >= -1.0
        assert float(bounds[1]) <= 1.0
    finally:
        con.close()
