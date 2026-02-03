from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema
from src.data.price_backfill import PriceBackfiller
from src.phase0.core.audit_engine import AuditEngine, BacktestConfig


class FakeProvider:
    name = "fake"

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        rng = pd.date_range(start, end, freq="D")
        return pd.DataFrame(
            {
                "date": [d.date() for d in rng],
                "open_price": [100.0] * len(rng),
                "price": [101.0] * len(rng),
            }
        )


def test_price_backfiller_upserts_prices_and_logs():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    bf = PriceBackfiller(con, providers=[FakeProvider()], max_window_days=10, write_audit_log=True)

    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    res = bf.backfill_prices("AAPL", start=start, end=end)

    assert res
    assert res[0].provider == "fake"
    assert res[0].status == "SUCCESS"

    # Window clamping: start + 10 days inclusive, but never beyond today's date
    expected_end = min((pd.Timestamp(start) + pd.Timedelta(days=10)).date(), date.today())
    expected_rows = len(pd.date_range(start, expected_end, freq="D"))

    n_prices = con.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAPL'").fetchone()[0]
    assert int(n_prices) == int(expected_rows)

    # Provenance columns are populated
    row = con.execute(
        "SELECT source, fetched_at FROM prices WHERE ticker='AAPL' ORDER BY date LIMIT 1"
    ).fetchone()
    assert row[0] == "fake"
    assert row[1] is not None

    # Audit log captured
    n_logs = con.execute("SELECT COUNT(*) FROM data_gaps").fetchone()[0]
    assert int(n_logs) >= 1


def test_audit_engine_backfill_injection():
    con = duckdb.connect(database=":memory:")
    ensure_schema(con)

    eng = AuditEngine(con=con)
    cfg = BacktestConfig(allow_online_backfill=True, backfill_window_days=5)

    trades = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "buy_date": ["2026-01-01"],
            "exit_is_fallback": [True],
        }
    )

    stats = eng.backfill_prices_for_forced_exits(trades, cfg, providers=[FakeProvider()])

    assert int(stats.get("backfill_forced_exits", 0)) == 1
    assert int(stats.get("backfill_attempts", 0)) == 1
    assert int(stats.get("backfill_rows_upserted", 0)) > 0

    n_prices = con.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAPL'").fetchone()[0]
    assert int(n_prices) > 0
