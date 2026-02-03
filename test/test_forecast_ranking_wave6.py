from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb

from src.forecast.ranking import generate_forecast_ranking, write_forecast_ranking_artifacts


def _seed_minimal_schema(con: duckdb.DuckDBPyConnection) -> None:
    # Minimal tables required by src.forecast.ranking (no schema migrations in tests).
    con.execute(
        """
        CREATE TABLE recs(
            date DATE,
            ticker VARCHAR,
            firm VARCHAR,
            rating VARCHAR,
            sentiment_score DOUBLE,
            headline VARCHAR,
            source_url VARCHAR,
            universe_id VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE prices(
            date DATE,
            ticker VARCHAR,
            close DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ticker_mappings(
            alias_ticker VARCHAR,
            canonical_ticker VARCHAR,
            start_date DATE,
            end_date DATE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE universe_membership(
            universe_id VARCHAR,
            ticker VARCHAR,
            start_date DATE,
            end_date DATE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE audit_trades(
            run_id VARCHAR,
            firm VARCHAR,
            rating VARCHAR,
            signal_date DATE,
            net_return_pct DOUBLE,
            gross_return_pct DOUBLE,
            exit_reason VARCHAR
        )
        """
    )


def test_forecast_no_future_leak_calibration_uses_signal_date_lt_asof() -> None:
    con = duckdb.connect(database=":memory:")
    try:
        _seed_minimal_schema(con)

        asof = date(2026, 1, 10)
        # Candidate signal on asof date.
        con.execute(
            "INSERT INTO recs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [asof, "AAA", "FIRM1", "BUY", 0.0, "AAA note", "", "ALL"],
        )
        con.execute("INSERT INTO universe_membership VALUES ('ALL','AAA',NULL,NULL)")
        # Price exists after signal_date => enterable.
        con.execute("INSERT INTO prices VALUES (DATE '2026-01-11','AAA',100.0)")

        # Calibration history: one row before asof, one row on asof (must be excluded).
        con.execute(
            "INSERT INTO audit_trades VALUES ('r0','FIRM1','BUY',DATE '2026-01-09',1.0,NULL,'NORMAL')"
        )
        con.execute(
            "INSERT INTO audit_trades VALUES ('r1','FIRM1','BUY',DATE '2026-01-10',100.0,NULL,'NORMAL')"
        )

        obj = generate_forecast_ranking(con, universe_id="ALL", asof_date=asof, top_n=25, run_id=None)
        assert obj["meta"]["asof_date"] == "2026-01-10"
        assert len(obj.get("rows") or []) == 1
        row = obj["rows"][0]
        # If future leak occurred, mean would be ~50.5 and the forecast would be very large.
        assert float(row["forecast_return_pct"]) < 10.0
        # And the bucket mean should match the pre-asof row (1.0).
        assert abs(float(row["calibration_bucket_mean_return_pct"]) - 1.0) < 1e-9
    finally:
        con.close()


def test_stars_are_percentile_based_and_deterministic() -> None:
    con = duckdb.connect(database=":memory:")
    try:
        _seed_minimal_schema(con)

        asof = date(2026, 1, 10)
        con.execute("INSERT INTO universe_membership VALUES ('ALL','AAA',NULL,NULL)")
        con.execute("INSERT INTO prices VALUES (DATE '2026-01-11','AAA',100.0)")

        # Create 10 signals with distinct sentiment scores so ordering is strict.
        # With no calibration history, forecast_return_pct = sentiment_score * 0.50.
        for i, s in enumerate([1.0, 0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8], start=1):
            ticker = f"AA{i}"
            con.execute("INSERT INTO universe_membership VALUES ('ALL', ?, NULL, NULL)", [ticker])
            con.execute("INSERT INTO prices VALUES (DATE '2026-01-11', ?, 100.0)", [ticker])
            con.execute(
                "INSERT INTO recs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [asof, ticker, "FIRM0", "BUY", float(s), f"{ticker} h", "", "ALL"],
            )

        obj = generate_forecast_ranking(con, universe_id="ALL", asof_date=asof, top_n=25, run_id=None)
        rows = obj.get("rows") or []
        assert len(rows) == 10

        # Stars distribution for n=10:
        # top 1 => 5★, next 2 => 4★, next 4 => 3★, next 2 => 2★, last 1 => 1★
        stars = [int(r["stars"]) for r in rows]
        assert stars == [5, 4, 4, 3, 3, 3, 3, 2, 2, 1]
        # Ranking must be stable: ranks are 1..n.
        ranks = [int(r["rank"]) for r in rows]
        assert ranks == list(range(1, 11))
    finally:
        con.close()


def test_writes_artifacts_and_updates_latest(tmp_path: Path) -> None:
    con = duckdb.connect(database=":memory:")
    try:
        _seed_minimal_schema(con)
        asof = date(2026, 1, 10)
        con.execute("INSERT INTO recs VALUES (DATE '2026-01-10','AAA','FIRM1','BUY',0.0,'h','', 'ALL')")
        con.execute("INSERT INTO universe_membership VALUES ('ALL','AAA',NULL,NULL)")
        con.execute("INSERT INTO prices VALUES (DATE '2026-01-11','AAA',100.0)")
        obj = generate_forecast_ranking(con, universe_id="ALL", asof_date=asof, run_id="RID123")
    finally:
        con.close()

    rep = tmp_path / "reports"
    paths = write_forecast_ranking_artifacts(obj, reports_dir=rep, run_id="RID123", asof_date=asof.isoformat(), top_n=25)
    assert (Path(paths["json"]).exists())
    assert (Path(paths["md"]).exists())
    assert (Path(paths["latest_json"]).exists())
    # Latest JSON should parse and match run_id.
    latest = json.loads(Path(paths["latest_json"]).read_text(encoding="utf-8"))
    assert latest.get("meta", {}).get("run_id") == "RID123"


def test_streamlit_page_import_is_offline_and_optional_dependency() -> None:
    # Streamlit may not be installed in the test environment; the page must still be importable.
    __import__("src.phase2.pages.06_Forecasts_Ranking")
