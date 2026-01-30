from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest


def _make_db(db_path: Path, *, universe_id: str = "ALL", ticker: str = "TSLA") -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE universe_membership (
                universe_id VARCHAR,
                ticker VARCHAR,
                start_date DATE,
                end_date DATE
            )
            """
        )
        con.execute(
            "INSERT INTO universe_membership VALUES (?, ?, DATE '2020-01-01', NULL)",
            [universe_id, ticker],
        )
    finally:
        con.close()


def test_collect_google_news_rss_offline_guard(monkeypatch, tmp_path: Path):
    """Online mode must be blocked unless NEWS_ALPHA_ALLOW_ONLINE=1."""

    monkeypatch.delenv("NEWS_ALPHA_ALLOW_ONLINE", raising=False)

    from src.news_alpha.collect_google_news_rss import main

    with pytest.raises(SystemExit) as e:
        main(
            [
                "--db",
                str(tmp_path / "dummy.db"),
                "--universe-id",
                "ALL",
                "--date-from",
                "2026-01-12",
                "--date-to",
                "2026-01-13",
                "--online",
            ]
        )

    assert "online mode is disabled" in str(e.value).lower()


def test_collect_google_news_rss_offline_parse_filters_and_outputs(tmp_path: Path):
    db_path = tmp_path / "sentinel.db"
    _make_db(db_path)

    # Raw RSS fixtures can use canonical or legacy naming.
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    fixture_xml = Path("test/fixtures/news_alpha/rss/google_news_TSLA_when14d.xml").read_text(encoding="utf-8")
    (raw_dir / "google_news_TSLA_when14d.xml").write_text(fixture_xml, encoding="utf-8")

    out_fixtures = tmp_path / "out.jsonl"
    out_stats = tmp_path / "stats.json"

    from src.news_alpha.collect_google_news_rss import main

    rc = main(
        [
            "--db",
            str(db_path),
            "--universe-id",
            "ALL",
            "--date-from",
            "2026-01-12",
            "--date-to",
            "2026-01-13",
            "--domains",
            "ilsole24ore.com",
            "--when-days",
            "14",
            "--raw-dir",
            str(raw_dir),
            "--offline-parse",
            "--out-fixtures",
            str(out_fixtures),
            "--stats-file",
            str(out_stats),
        ]
    )
    assert rc == 0

    lines = out_fixtures.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    row = json.loads(lines[0])
    assert row["tickers"] == ["TSLA"]
    assert row["source"] == "Il Sole 24 ORE"
    assert row["published_at"].startswith("2026-01-13T")
    assert "<" not in row.get("headline", "")

    # Integration check: output fixtures must be consumable by the fixtures loader.
    from src.news_alpha.fixtures import load_fixtures_jsonl

    items = list(load_fixtures_jsonl(out_fixtures))
    assert len(items) == 1
    assert items[0].headline
    assert items[0].published_at.startswith("2026-01-13T")

    stats = json.loads(out_stats.read_text(encoding="utf-8"))
    assert stats["items_raw"] == 3
    assert stats["items_kept"] == 1
    assert stats["items_rej_domain"] == 1
    assert stats["items_rej_date"] == 1


def test_collect_google_news_rss_offline_parse_accepts_legacy_filename(tmp_path: Path):
    """Collector must accept historical raw XML naming: google_news_<TICKER>.xml."""

    db_path = tmp_path / "sentinel.db"
    _make_db(db_path)

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    fixture_xml = Path("test/fixtures/news_alpha/rss/google_news_TSLA_when14d.xml").read_text(encoding="utf-8")
    # Legacy: no `whenXd` suffix.
    (raw_dir / "google_news_TSLA.xml").write_text(fixture_xml, encoding="utf-8")

    out_fixtures = tmp_path / "out.jsonl"
    out_stats = tmp_path / "stats.json"

    from src.news_alpha.collect_google_news_rss import main

    rc = main(
        [
            "--db",
            str(db_path),
            "--universe-id",
            "ALL",
            "--date-from",
            "2026-01-12",
            "--date-to",
            "2026-01-13",
            "--domains",
            "ilsole24ore.com",
            "--when-days",
            "14",
            "--raw-dir",
            str(raw_dir),
            "--offline-parse",
            "--out-fixtures",
            str(out_fixtures),
            "--stats-file",
            str(out_stats),
        ]
    )
    assert rc == 0

    lines = out_fixtures.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    stats = json.loads(out_stats.read_text(encoding="utf-8"))
    assert stats["items_kept"] == 1
    assert stats["tickers_requested"] == 1
    assert stats["tickers_with_raw"] == 1
