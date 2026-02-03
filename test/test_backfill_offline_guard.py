from __future__ import annotations

from datetime import date

import duckdb

import src.data.price_backfill as pb
from src.data.price_backfill import PriceBackfiller
from src.phase0.db.migrate import ensure_schema


class _FailRequests:
    @staticmethod
    def get(*args, **kwargs):
        raise AssertionError("network call attempted via requests.get")


class _FailYF:
    @staticmethod
    def download(*args, **kwargs):
        raise AssertionError("network call attempted via yfinance.download")


def test_backfill_prices_offline_guard_skips_network_and_logs(monkeypatch):
    monkeypatch.setenv("SENTINEL_OFFLINE", "1")
    monkeypatch.delenv("SENTINEL_ALLOW_ONLINE_BACKFILL", raising=False)

    # Force the presence of network entrypoints and make them fail hard if called.
    monkeypatch.setattr(pb, "requests", _FailRequests(), raising=False)
    monkeypatch.setattr(pb, "yf", _FailYF(), raising=False)

    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    bf = PriceBackfiller(con, providers=None, max_window_days=30, write_audit_log=True)

    res = bf.backfill_prices("AAPL", start=date(2026, 1, 1), end=date(2026, 1, 5))
    assert res == []

    n_prices = con.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAPL'").fetchone()[0]
    assert int(n_prices) == 0

    row = con.execute(
        "SELECT status, reason_code, provider, message FROM data_gaps ORDER BY requested_at DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == "SKIPPED"
    assert row[1] == "OFFLINE"
    assert row[2] == "system"
    assert "OFFLINE" in str(row[3]).upper()
