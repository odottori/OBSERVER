from __future__ import annotations

"""Seed market_halts from the normalized closures CSV.

The input CSV contains one row per (date,exchange). We map exchanges to the
internal `market` label (see `config/dataops/exchange_to_market.yml`) and then
store *market-wide* closure intervals in `market_halts`.

IMPORTANT
---------
If multiple exchanges map to the same market label, the seed becomes an
approximation (union of closure days). This is acceptable for PHASE1 data-quality
workflows. If you need per-exchange precision, refine the mapping and align
`metadata.market` accordingly.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from .common import timing
from .paths import closures_csv_path, exchange_to_market_path


@dataclass(frozen=True)
class SeedResult:
    rows_inserted: int
    markets: int
    status: str
    message: str


def _load_mapping(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    obj = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in obj.items():
        if k is None or v is None:
            continue
        out[str(k).strip().upper()] = str(v).strip().upper()
    return out


def _compress_consecutive(ds: list[date]) -> list[tuple[date, date]]:
    if not ds:
        return []
    ds = sorted(ds)
    out: list[tuple[date, date]] = []
    cur_start = ds[0]
    cur_end = ds[0]
    for d in ds[1:]:
        if (pd.Timestamp(d) - pd.Timestamp(cur_end)).days == 1:
            cur_end = d
        else:
            out.append((cur_start, cur_end))
            cur_start = d
            cur_end = d
    out.append((cur_start, cur_end))
    return out


def seed_market_halts_from_csv(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    csv_path: Path | None = None,
    mapping_path: Path | None = None,
    source: str = "SEED_CLOSURES_CSV",
    replace_seed: bool = True,
) -> SeedResult:
    csv_path = csv_path or closures_csv_path()
    mapping_path = mapping_path or exchange_to_market_path()

    with timing() as t_ms:
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            return SeedResult(0, 0, "FAILED", f"cannot read csv: {e}")

        if df is None or df.empty:
            return SeedResult(0, 0, "SKIPPED", "csv empty")

        # Normalize
        for col in ["date", "exchange"]:
            if col not in df.columns:
                return SeedResult(0, 0, "FAILED", f"missing column: {col}")

        df["exchange"] = df["exchange"].astype(str).str.strip().str.upper()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df = df.dropna(subset=["date", "exchange"])
        if df.empty:
            return SeedResult(0, 0, "FAILED", "no parseable rows")

        # Weekend sanity (keep rows, but warn via message)
        weekend_n = int(pd.to_datetime(df["date"]).dt.dayofweek.isin([5, 6]).sum())

        mapping = _load_mapping(mapping_path)
        if not mapping:
            return SeedResult(0, 0, "FAILED", f"missing/invalid mapping: {mapping_path}")

        df["market"] = df["exchange"].map(mapping)
        missing_map = df["market"].isna().sum()
        df = df.dropna(subset=["market"])
        df["market"] = df["market"].astype(str).str.strip().str.upper()

        if df.empty:
            return SeedResult(0, 0, "FAILED", "all exchanges missing mapping")

        # Union per market and compress
        inserts: list[tuple[str, date, date, str, str]] = []
        markets = sorted(df["market"].unique().tolist())
        for m in markets:
            dates = sorted(df.loc[df["market"] == m, "date"].tolist())
            # Dedup
            dates = sorted(set(dates))
            for start, end in _compress_consecutive(dates):
                inserts.append((m, start, end, "MARKET_CLOSED", source))

        # Apply
        try:
            con.execute("BEGIN")
            if replace_seed:
                con.execute("DELETE FROM market_halts WHERE source = ?", [source])

            # Insert/Upsert
            con.register("df_mkt_halts", pd.DataFrame(inserts, columns=["market", "start_date", "end_date", "reason", "source"]))
            con.execute(
                """
                INSERT INTO market_halts(market, start_date, end_date, reason, source)
                SELECT market, start_date, end_date, reason, source FROM df_mkt_halts
                ON CONFLICT(market, start_date) DO UPDATE SET
                  end_date=excluded.end_date,
                  reason=excluded.reason,
                  source=excluded.source
                """
            )
            con.execute("COMMIT")
        except Exception as e:
            try:
                con.execute("ROLLBACK")
            except Exception:
                pass
            return SeedResult(0, 0, "FAILED", f"db write failed: {e}")

        rows_inserted = len(inserts)
        msg = f"seeded {rows_inserted} market_halts intervals from {csv_path.name}; markets={len(markets)}"
        if missing_map:
            msg += f"; missing_mapping_rows={int(missing_map)}"
        if weekend_n:
            msg += f"; weekend_rows={weekend_n} (check input)"

        # Best-effort operational log to data_gaps
        try:
            con.execute(
                """
                INSERT INTO data_gaps(run_id, kind, ticker, start_date, end_date, requested_at, status, provider, message, rows_inserted, rows_upserted, duration_ms, reason_code)
                VALUES (?, 'calendar', NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    datetime.now(timezone.utc),
                    "SUCCESS",
                    "seed_closures",
                    msg[:500],
                    rows_inserted,
                    rows_inserted,
                    t_ms(),
                    "SUCCESS",
                ],
            )
        except Exception:
            pass

        return SeedResult(rows_inserted, len(markets), "SUCCESS", msg)
