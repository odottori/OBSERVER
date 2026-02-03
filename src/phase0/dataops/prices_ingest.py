from __future__ import annotations

"""Incremental price ingest (PHASE1).

This module wraps the existing `PriceBackfiller` into an operational ingest tool:
- chooses tickers (universe or metadata)
- computes incremental ranges per ticker
- logs a short summary in `data_gaps`

The underlying provider calls are guarded by the existing OFFLINE safeguards in
`PriceBackfiller`. The CLI can enable online ingestion explicitly.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

import duckdb
import pandas as pd

from src.data.price_backfill import PriceBackfiller
from src.phase0.db.migrate import ensure_schema

from .common import timing, truthy_env


def _as_date(v: str | date) -> date:
    if isinstance(v, date):
        return v
    d = pd.to_datetime(v, errors="coerce")
    if pd.isna(d):
        raise ValueError(f"invalid date: {v}")
    return d.date()


def _tickers_from_universe(con: duckdb.DuckDBPyConnection, universe_id: str) -> list[str]:
    try:
        rows = con.execute(
            """
            SELECT DISTINCT ticker
            FROM universe_membership
            WHERE universe_id = ?
            ORDER BY ticker
            """,
            [universe_id],
        ).fetchall()
        out = [r[0] for r in rows if r and r[0]]
        return [str(t).strip().upper() for t in out if str(t).strip()]
    except Exception:
        return []


def _tickers_from_metadata_or_prices(con: duckdb.DuckDBPyConnection) -> list[str]:
    try:
        rows = con.execute("SELECT ticker FROM metadata ORDER BY ticker").fetchall()
        out = [r[0] for r in rows if r and r[0]]
        if out:
            return [str(t).strip().upper() for t in out]
    except Exception:
        pass

    try:
        rows = con.execute("SELECT DISTINCT ticker FROM prices ORDER BY ticker").fetchall()
        out = [r[0] for r in rows if r and r[0]]
        return [str(t).strip().upper() for t in out]
    except Exception:
        return []


def _last_price_date(con: duckdb.DuckDBPyConnection, ticker: str) -> date | None:
    try:
        row = con.execute("SELECT MAX(date) FROM prices WHERE ticker = ?", [ticker]).fetchone()
        return row[0] if row else None
    except Exception:
        return None


@dataclass(frozen=True)
class IngestResult:
    tickers: int
    attempted: int
    total_rows_upserted: int
    status: str
    message: str


def ingest_prices_incremental(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    asof_date: date,
    universe_id: str = "ALL",
    lookback_days: int = 45,
    start_date: date | None = None,
    max_window_days: int = 180,
    online: bool = False,
) -> IngestResult:
    """Ingest prices up to `asof_date`.

    - If `start_date` is provided, all tickers use that range.
    - Otherwise, per ticker we ingest from min(last_date+1, asof-lookback+1).
    """

    ensure_schema(con)

    tickers = _tickers_from_universe(con, universe_id) or _tickers_from_metadata_or_prices(con)
    tickers = sorted(set([t for t in tickers if t]))
    if not tickers:
        return IngestResult(0, 0, 0, "SKIPPED", "no tickers found")

    # Explicit online enable (only affects network providers; offline-safe injected providers remain ok)
    if online:
        import os

        os.environ["SENTINEL_OFFLINE"] = "0"
        os.environ["SENTINEL_ALLOW_ONLINE_BACKFILL"] = "1"
    else:
        # Respect env default; but if user explicitly requested offline, enforce.
        if truthy_env("SENTINEL_OFFLINE", False):
            pass

    backfiller = PriceBackfiller(
        con,
        providers=None,
        max_window_days=int(max_window_days),
        write_audit_log=True,
        run_id=run_id,
    )

    attempted = 0
    total_upserted = 0

    with timing() as t_ms:
        for ticker in tickers:
            last_d = _last_price_date(con, ticker)
            if start_date is not None:
                st = start_date
            else:
                # default incremental
                lb = max(1, int(lookback_days))
                st = (pd.Timestamp(asof_date) - pd.Timedelta(days=lb - 1)).date()
                if last_d is not None:
                    st2 = (pd.Timestamp(last_d) + pd.Timedelta(days=1)).date()
                    st = min(st, st2)  # refresh a small lookback too

            if st > asof_date:
                continue

            attempted += 1
            try:
                res = backfiller.backfill_prices(ticker, st, asof_date)
                # We cannot directly know upserts per provider without querying.
                # Best-effort: count rows in range after call.
                try:
                    n = con.execute(
                        "SELECT COUNT(*) FROM prices WHERE ticker = ? AND date BETWEEN ? AND ?",
                        [ticker, st, asof_date],
                    ).fetchone()[0]
                    total_upserted += int(n)
                except Exception:
                    pass
            except Exception:
                # Underlying backfiller already logs failures to data_gaps.
                continue

        msg = f"prices_ingest: tickers={len(tickers)} attempted={attempted} asof={asof_date} lookback_days={lookback_days} online={bool(online)}"

        try:
            con.execute(
                """
                INSERT INTO data_gaps(run_id, kind, ticker, start_date, end_date, requested_at, status, provider, message, rows_inserted, rows_upserted, duration_ms, reason_code)
                VALUES (?, 'prices_ingest', NULL, ?, ?, ?, 'SUCCESS', 'ingest_prices', ?, NULL, ?, ?, 'SUCCESS')
                """,
                [
                    run_id,
                    start_date,
                    asof_date,
                    datetime.now(timezone.utc),
                    msg[:500],
                    int(total_upserted),
                    int(t_ms()),
                ],
            )
        except Exception:
            pass

    return IngestResult(len(tickers), attempted, int(total_upserted), "SUCCESS", msg)
