from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
import pytest

# Ensure repo root (containing `src/`) is importable when running standalone.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.news_alpha.run import main as news_alpha_main  # noqa: E402


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


def test_offline_guard_blocks_online_without_env(tmp_path: Path) -> None:
    db_path = tmp_path / "t.duckdb"
    _make_min_db(db_path)

    fixtures = (Path(__file__).resolve().parent / "fixtures" / "news_alpha" / "basic.jsonl")
    assert fixtures.exists()

    os.environ.pop("NEWS_ALPHA_ALLOW_ONLINE", None)

    with pytest.raises(SystemExit) as excinfo:
        news_alpha_main(
            [
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
                "--online",
            ]
        )

    msg = str(excinfo.value)
    assert "NEWS_ALPHA_ALLOW_ONLINE=1" in msg
