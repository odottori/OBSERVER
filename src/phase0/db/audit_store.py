"""Audit-grade persistence for certification runs.

Purpose
-------
SENTINEL-ALPHA is designed to be *certifiable*.
That means every pipeline run must be reproducible and auditable:

- Stable run identifier (run_id)
- Immutable artifacts persisted to DuckDB (trades + equity curve)
- Provenance of online backfill attempts (data_gaps)

This module is intentionally small and dependency-free.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


def compute_code_fingerprint(project_root: str | Path | None = None) -> str:
    """Compute a stable fingerprint of the *core* logic.

    This is not a git hash (git may not be present). It is a SHA-256 over the
    bytes of a curated set of source files that materially affect results.
    """

    root = Path(project_root) if project_root else Path.cwd()
    candidates = [
        root / "main.py",
        root / "src" / "intelligence_engine.py",
        root / "src" / "core" / "audit_engine.py",
        root / "src" / "core" / "cost_model.py",
        root / "src" / "core" / "tax_model.py",
        root / "src" / "data" / "price_backfill.py",
        root / "src" / "db" / "migrate.py",
    ]

    h = hashlib.sha256()
    for p in candidates:
        try:
            b = p.read_bytes()
        except Exception:
            continue
        h.update(p.name.encode("utf-8", errors="ignore"))
        h.update(b)
    return h.hexdigest()


def start_audit_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    universe_id: str,
    holding_period_sessions: int,
    cfg_obj: object | None = None,
    notes: str | None = None,
    project_root: str | Path | None = None,
) -> None:
    """Insert a new row into audit_runs (idempotent per run_id)."""

    started_at = datetime.now(timezone.utc)
    cfg_json = None
    if cfg_obj is not None:
        try:
            cfg_json = json.dumps(asdict(cfg_obj), sort_keys=True)
        except Exception:
            try:
                cfg_json = json.dumps(cfg_obj, sort_keys=True)
            except Exception:
                cfg_json = None

    con.execute(
        """
        INSERT INTO audit_runs(
            run_id, started_at, finished_at, status,
            universe_id, holding_period_sessions,
            config_json, code_fingerprint, notes, error
        )
        VALUES (?, ?, NULL, 'RUNNING', ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(run_id) DO NOTHING
        """,
        [
            run_id,
            started_at,
            universe_id,
            int(holding_period_sessions),
            cfg_json,
            compute_code_fingerprint(project_root),
            (notes or None),
        ],
    )


def finish_audit_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    status: str,
    error: str | None = None,
) -> None:
    finished_at = datetime.now(timezone.utc)
    con.execute(
        """
        UPDATE audit_runs
        SET finished_at = ?, status = ?, error = ?
        WHERE run_id = ?
        """,
        [finished_at, str(status).upper(), (error[:500] if error else None), run_id],
    )


def _trade_id(run_id: str, row: pd.Series) -> str:
    key = "|".join(
        [
            str(run_id),
            str(row.get("ticker", "")),
            str(row.get("firm", "")),
            str(row.get("signal_date", "")),
            str(row.get("buy_date", "")),
            str(row.get("sell_date", "")),
            str(row.get("rating", "")),
        ]
    )
    return hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()


def persist_trades(con: duckdb.DuckDBPyConnection, run_id: str, trades_df: pd.DataFrame) -> int:
    """Persist executed trades for a certification run.

    The insert is resilient to schema evolution by:
    - adding missing columns to the dataframe
    - inserting with an explicit column list
    """

    if trades_df is None or trades_df.empty:
        return 0

    df = trades_df.copy()

    # Normalize dates
    for c in ["signal_date", "buy_date", "sell_date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

    df["run_id"] = str(run_id)
    df["trade_id"] = df.apply(lambda r: _trade_id(run_id, r), axis=1)

    # Column order matches `audit_trades` schema (see src/db/migrate.py)
    cols = [
        "trade_id",
        "run_id",
        "signal_date",
        "buy_date",
        "sell_date",
        "exit_reason",
        "exit_is_fallback",
        "ticker",
        "ticker_original",
        "firm",
        "rating",
        "market",
        "sector",
        "instrument_type",
        "mom_status",
        "risk_vol",
        "is_tobin_tax",
        "ftt_pct",
        "sentiment_score",
        "exec_shift_sessions",
        "exit_shift_sessions",
        "halt_reason",
        "buy_price",
        "sell_price",
        "gross_return_pct",
        "cost_pct",
        "net_return_pct",
        "trade_score",
        "universe_id",
    ]

    # Ensure all expected columns exist.
    for c in cols:
        if c not in df.columns:
            df[c] = None

    df = df[cols].copy()

    con.register("df_audit_trades", df)
    col_list = ",".join(cols)
    con.execute(
        f"""
        INSERT INTO audit_trades({col_list})
        SELECT {col_list} FROM df_audit_trades
        ON CONFLICT(trade_id) DO NOTHING
        """
    )
    try:
        con.unregister("df_audit_trades")
    except Exception:
        pass
    return int(len(df))


def persist_equity(con: duckdb.DuckDBPyConnection, run_id: str, equity_df: pd.DataFrame) -> int:
    if equity_df is None or equity_df.empty:
        return 0

    df = equity_df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["run_id"] = str(run_id)


    # Backward compatibility: older equity curves may use open_positions.
    if "positions" not in df.columns and "open_positions" in df.columns:
        df["positions"] = df["open_positions"]

    # Derive invested if missing (equity = cash + invested).
    if "invested" not in df.columns and "equity" in df.columns and "cash" in df.columns:
        df["invested"] = pd.to_numeric(df["equity"], errors="coerce") - pd.to_numeric(df["cash"], errors="coerce")

    # Normalize numeric fields
    if "positions" in df.columns:
        df["positions"] = pd.to_numeric(df["positions"], errors="coerce").fillna(0).astype(int)
    if "invested" in df.columns:
        df["invested"] = pd.to_numeric(df["invested"], errors="coerce").fillna(0.0).astype(float)

    cols = [
        "run_id",
        "date",
        "equity",
        "cash",
        "invested",
        "positions",
        "tax_paid",
        "executed_trades",
        "closed_trades",
    ]

    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()

    con.register("df_audit_equity", df)
    con.execute(
        """
        INSERT INTO audit_equity
        SELECT * FROM df_audit_equity
        ON CONFLICT(run_id, date) DO UPDATE SET
          equity=excluded.equity,
          cash=excluded.cash,
          invested=excluded.invested,
          positions=excluded.positions,
          tax_paid=excluded.tax_paid,
          executed_trades=excluded.executed_trades,
          closed_trades=excluded.closed_trades
        """
    )
    return int(len(df))


def backfill_summary(con: duckdb.DuckDBPyConnection, run_id: str) -> pd.DataFrame:
    """Return provider/status-level aggregation for a run."""

    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info('data_gaps')").fetchall()}
        has_upserted = "rows_upserted" in cols
    except Exception:
        has_upserted = False

    try:
        if has_upserted:
            return con.execute(
                """
                SELECT
                  provider,
                  status,
                  COUNT(*) AS attempts,
                  SUM(COALESCE(rows_inserted,0)) AS rows_inserted_total,
                  SUM(COALESCE(rows_upserted,0)) AS rows_upserted_total,
                  SUM(GREATEST(COALESCE(rows_upserted,0) - COALESCE(rows_inserted,0), 0)) AS rows_updated_est,
                  ROUND(AVG(COALESCE(duration_ms,0)), 2) AS avg_duration_ms
                FROM data_gaps
                WHERE run_id = ?
                GROUP BY 1,2
                ORDER BY attempts DESC
                """,
                [run_id],
            ).df()

        return con.execute(
            """
            SELECT
              provider,
              status,
              COUNT(*) AS attempts,
              SUM(COALESCE(rows_inserted,0)) AS rows_inserted_total,
              ROUND(AVG(COALESCE(duration_ms,0)), 2) AS avg_duration_ms
            FROM data_gaps
            WHERE run_id = ?
            GROUP BY 1,2
            ORDER BY attempts DESC
            """,
            [run_id],
        ).df()
    except Exception:
        return pd.DataFrame()
