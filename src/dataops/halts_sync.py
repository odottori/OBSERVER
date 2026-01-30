from __future__ import annotations

"""Sync manual halts overlay (halts.yml) into DuckDB.

This sync maintains two tables:
- market_halts
- ticker_halts

The input file is intended to be human-editable and may be updated via the
Streamlit Control Room.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

from .common import timing
from .paths import halts_yaml_path


@dataclass(frozen=True)
class SyncResult:
    market_rows: int
    ticker_rows: int
    status: str
    message: str


def _norm_date(v: Any) -> date | None:
    try:
        d = pd.to_datetime(v, errors="coerce")
        if pd.isna(d):
            return None
        return d.date()
    except Exception:
        return None


def _load(path: Path) -> dict:
    obj = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(obj, dict):
        return {}
    return obj


def sync_halts_yaml(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    yaml_path: Path | None = None,
    default_source: str = "MANUAL:halts.yml",
    replace_previous: bool = True,
) -> SyncResult:
    yaml_path = yaml_path or halts_yaml_path()

    with timing() as t_ms:
        if not yaml_path.exists():
            return SyncResult(0, 0, "SKIPPED", f"missing file: {yaml_path}")

        cfg = _load(yaml_path)
        ver = int(cfg.get("version") or 0)
        if ver != 1:
            return SyncResult(0, 0, "FAILED", f"unsupported halts.yml version: {ver}")

        mkt = cfg.get("market_halts") or []
        tkr = cfg.get("ticker_halts") or []
        if not isinstance(mkt, list) or not isinstance(tkr, list):
            return SyncResult(0, 0, "FAILED", "invalid YAML structure")

        mkt_rows: list[tuple[str, date, date, str, str]] = []
        for it in mkt:
            if not isinstance(it, dict):
                continue
            market = str(it.get("market") or "").strip().upper()
            sd = _norm_date(it.get("start_date"))
            ed = _norm_date(it.get("end_date")) or sd
            if not market or not sd:
                continue
            if ed and ed < sd:
                sd, ed = ed, sd
            reason = str(it.get("reason") or "MANUAL_HALT").strip()[:200]
            source = str(it.get("source") or default_source).strip()[:80]
            mkt_rows.append((market, sd, ed or sd, reason, source))

        tkr_rows: list[tuple[str, date, date, str, str]] = []
        for it in tkr:
            if not isinstance(it, dict):
                continue
            ticker = str(it.get("ticker") or "").strip().upper()
            sd = _norm_date(it.get("start_date"))
            ed = _norm_date(it.get("end_date")) or sd
            if not ticker or not sd:
                continue
            if ed and ed < sd:
                sd, ed = ed, sd
            reason = str(it.get("reason") or "MANUAL_HALT").strip()[:200]
            source = str(it.get("source") or default_source).strip()[:80]
            tkr_rows.append((ticker, sd, ed or sd, reason, source))

        try:
            con.execute("BEGIN")
            if replace_previous:
                con.execute("DELETE FROM market_halts WHERE source = ?", [default_source])
                con.execute("DELETE FROM ticker_halts WHERE source = ?", [default_source])

            if mkt_rows:
                con.register(
                    "df_mkt_manual",
                    pd.DataFrame(mkt_rows, columns=["market", "start_date", "end_date", "reason", "source"]),
                )
                con.execute(
                    """
                    INSERT INTO market_halts(market, start_date, end_date, reason, source)
                    SELECT market, start_date, end_date, reason, source FROM df_mkt_manual
                    ON CONFLICT(market, start_date) DO UPDATE SET
                      end_date=excluded.end_date,
                      reason=excluded.reason,
                      source=excluded.source
                    """
                )

            if tkr_rows:
                con.register(
                    "df_tkr_manual",
                    pd.DataFrame(tkr_rows, columns=["ticker", "start_date", "end_date", "reason", "source"]),
                )
                con.execute(
                    """
                    INSERT INTO ticker_halts(ticker, start_date, end_date, reason, source)
                    SELECT ticker, start_date, end_date, reason, source FROM df_tkr_manual
                    ON CONFLICT(ticker, start_date) DO UPDATE SET
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
            return SyncResult(0, 0, "FAILED", f"db write failed: {e}")

        msg = f"synced halts.yml: market_rows={len(mkt_rows)}, ticker_rows={len(tkr_rows)}"

        # Best-effort operational log
        try:
            con.execute(
                """
                INSERT INTO data_gaps(run_id, kind, ticker, start_date, end_date, requested_at, status, provider, message, rows_inserted, rows_upserted, duration_ms, reason_code)
                VALUES (?, 'calendar', NULL, NULL, NULL, ?, 'SUCCESS', 'sync_halts', ?, ?, ?, ?, 'SUCCESS')
                """,
                [
                    run_id,
                    datetime.now(timezone.utc),
                    msg[:500],
                    len(mkt_rows) + len(tkr_rows),
                    len(mkt_rows) + len(tkr_rows),
                    t_ms(),
                ],
            )
        except Exception:
            pass

        return SyncResult(len(mkt_rows), len(tkr_rows), "SUCCESS", msg)
