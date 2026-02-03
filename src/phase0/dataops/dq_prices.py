from __future__ import annotations

"""Price data quality (halt-aware).

Checks (PHASE1)
---------------
- Missing prices over an expected business-day calendar, excluding:
  - market_halts intervals for the ticker's market
  - ticker_halts intervals for the ticker
- Invalid prices: price <= 0 or NULL
- Staleness: last available price date is behind asof and there are expected
  sessions after that date

Results are written to DuckDB:
- dq_runs (kind='DQ_PRICES')
- dq_findings
- dq_metrics_daily
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema

from .common import now_utc, timing


def _as_date(v: str | date) -> date:
    if isinstance(v, date):
        return v
    d = pd.to_datetime(v, errors="coerce")
    if pd.isna(d):
        raise ValueError(f"invalid date: {v}")
    return d.date()


def _market_for_tickers(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return columns: ticker, market.

    Market falls back to EU/US heuristic if not present.
    """
    try:
        df = con.execute(
            """
            SELECT ticker,
                   COALESCE(NULLIF(TRIM(market), ''), CASE WHEN ticker LIKE '%.%' THEN 'EU' ELSE 'US' END) AS market
            FROM metadata
            """
        ).df()
        if df is not None and not df.empty:
            df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
            df["market"] = df["market"].astype(str).str.strip().str.upper()
            return df.dropna(subset=["ticker", "market"])
    except Exception:
        pass

    df = con.execute(
        """
        SELECT DISTINCT ticker,
               CASE WHEN ticker LIKE '%.%' THEN 'EU' ELSE 'US' END AS market
        FROM prices
        """
    ).df()
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["market"] = df["market"].astype(str).str.strip().str.upper()
    return df.dropna(subset=["ticker", "market"])


def _expand_intervals(df: pd.DataFrame, key_col: str, start_col: str, end_col: str, start_d: date, end_d: date) -> dict[str, set[date]]:
    out: dict[str, set[date]] = {}
    if df is None or df.empty:
        return out

    for _, r in df.iterrows():
        key = str(r.get(key_col) or "").strip().upper()
        sd = pd.to_datetime(r.get(start_col), errors="coerce")
        ed = pd.to_datetime(r.get(end_col), errors="coerce")
        if not key or pd.isna(sd):
            continue
        sd_d = sd.date()
        ed_d = (ed.date() if not pd.isna(ed) else sd_d)
        if ed_d < sd_d:
            sd_d, ed_d = ed_d, sd_d
        # clamp
        a = max(sd_d, start_d)
        b = min(ed_d, end_d)
        if b < a:
            continue
        # expand (range length is small in PHASE1 windows)
        ds = pd.date_range(a, b, freq="D").date
        out.setdefault(key, set()).update(set(ds))
    return out


def _compress_dates(dates: list[date]) -> list[tuple[date, date]]:
    if not dates:
        return []
    dates = sorted(set(dates))
    out: list[tuple[date, date]] = []
    cur_s = dates[0]
    cur_e = dates[0]
    for d in dates[1:]:
        if (pd.Timestamp(d) - pd.Timestamp(cur_e)).days == 1:
            cur_e = d
        else:
            out.append((cur_s, cur_e))
            cur_s = d
            cur_e = d
    out.append((cur_s, cur_e))
    return out


@dataclass(frozen=True)
class DqResult:
    status: str
    message: str
    missing_tickers: int
    invalid_rows: int
    stale_tickers: int


def run_price_data_quality(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    asof_date: date,
    window_days: int = 365,
    severity_missing: str = "WARN",
) -> DqResult:
    ensure_schema(con)

    asof_date = _as_date(asof_date)
    window_days = max(5, int(window_days))
    start_d = (pd.Timestamp(asof_date) - pd.Timedelta(days=window_days - 1)).date()

    with timing() as t_ms:
        started = now_utc()
        # calendar (business days)
        cal = pd.date_range(start_d, asof_date, freq="B").date
        cal_set = set(cal)

        tm = _market_for_tickers(con)
        if tm.empty:
            return DqResult("SKIPPED", "no tickers/markets found", 0, 0, 0)

        # fetch halts
        mkt_h = con.execute(
            """
            SELECT market, start_date, end_date
            FROM market_halts
            WHERE end_date >= ? AND start_date <= ?
            """,
            [start_d, asof_date],
        ).df()
        tkr_h = con.execute(
            """
            SELECT ticker, start_date, end_date
            FROM ticker_halts
            WHERE end_date >= ? AND start_date <= ?
            """,
            [start_d, asof_date],
        ).df()

        mkt_excl = _expand_intervals(mkt_h, "market", "start_date", "end_date", start_d, asof_date)
        tkr_excl = _expand_intervals(tkr_h, "ticker", "start_date", "end_date", start_d, asof_date)

        # existing price dates by ticker
        px = con.execute(
            """
            SELECT ticker, date
            FROM prices
            WHERE date BETWEEN ? AND ?
            """,
            [start_d, asof_date],
        ).df()
        if px is None:
            px = pd.DataFrame(columns=["ticker", "date"])
        if not px.empty:
            px["ticker"] = px["ticker"].astype(str).str.strip().str.upper()
            px["date"] = pd.to_datetime(px["date"], errors="coerce").dt.date
            px = px.dropna(subset=["ticker", "date"])

        px_by_ticker: dict[str, set[date]] = {}
        if not px.empty:
            for t, g in px.groupby("ticker"):
                px_by_ticker[str(t).strip().upper()] = set(g["date"].tolist())

        # invalid rows
        invalid_rows = 0
        try:
            invalid_rows = int(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM prices
                    WHERE date BETWEEN ? AND ? AND (price IS NULL OR price <= 0)
                    """,
                    [start_d, asof_date],
                ).fetchone()[0]
            )
        except Exception:
            invalid_rows = 0

        findings: list[dict[str, Any]] = []
        missing_tickers = 0
        stale_tickers = 0

        # iterate tickers
        for _, r in tm.iterrows():
            ticker = str(r["ticker"]).strip().upper()
            market = str(r["market"]).strip().upper()
            expected = set(cal_set)
            expected -= mkt_excl.get(market, set())
            expected -= tkr_excl.get(ticker, set())

            have = px_by_ticker.get(ticker, set())
            missing = sorted(expected - have)

            if missing:
                missing_tickers += 1
                for s, e in _compress_dates(missing):
                    findings.append(
                        dict(
                            kind="PRICE_MISSING",
                            severity=str(severity_missing).strip().upper(),
                            market=market,
                            ticker=ticker,
                            start_date=s,
                            end_date=e,
                            count=int((pd.Timestamp(e) - pd.Timestamp(s)).days) + 1,
                            message=f"missing prices for {ticker} ({market})",
                        )
                    )

            # staleness: last have date vs expected
            if expected:
                last_expected = max(expected)
                last_have = max(have) if have else None
                if last_have is None:
                    # already covered by missing; mark as stale too (optional)
                    if expected:
                        stale_tickers += 1
                        findings.append(
                            dict(
                                kind="PRICE_STALE",
                                severity="WARN",
                                market=market,
                                ticker=ticker,
                                start_date=min(expected),
                                end_date=last_expected,
                                count=len(expected),
                                message=f"no prices in window for {ticker}",
                            )
                        )
                else:
                    # only if there are expected sessions after last_have
                    if last_have < last_expected:
                        stale = sorted([d for d in expected if d > last_have])
                        if stale:
                            stale_tickers += 1
                            s, e = _compress_dates(stale)[0]
                            findings.append(
                                dict(
                                    kind="PRICE_STALE",
                                    severity="WARN",
                                    market=market,
                                    ticker=ticker,
                                    start_date=s,
                                    end_date=e,
                                    count=len(stale),
                                    message=f"stale since {last_have} (expected sessions after)",
                                )
                            )

        # write run + findings + metrics
        finished = now_utc()
        status = "SUCCESS"
        notes = f"window_days={window_days}; tickers={len(tm)}; missing_tickers={missing_tickers}; stale_tickers={stale_tickers}; invalid_rows={invalid_rows}"

        try:
            con.execute(
                """
                INSERT INTO dq_runs(run_id, kind, started_at, finished_at, asof_date, window_days, status, notes, error)
                VALUES (?, 'DQ_PRICES', ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(run_id) DO UPDATE SET
                  kind=excluded.kind,
                  started_at=excluded.started_at,
                  finished_at=excluded.finished_at,
                  asof_date=excluded.asof_date,
                  window_days=excluded.window_days,
                  status=excluded.status,
                  notes=excluded.notes,
                  error=excluded.error
                """,
                [run_id, started, finished, asof_date, int(window_days), status, notes[:500]],
            )
        except Exception:
            pass

        # purge previous findings for same run_id (idempotence)
        try:
            con.execute("DELETE FROM dq_findings WHERE run_id = ?", [run_id])
        except Exception:
            pass

        # insert findings
        if findings:
            out = pd.DataFrame(findings)
            out["run_id"] = run_id
            out["finding_id"] = [f"F_{run_id}_{i:05d}" for i in range(len(out))]
            out["created_at"] = datetime.now(timezone.utc)
            con.register("df_findings", out[["finding_id", "run_id", "kind", "severity", "market", "ticker", "start_date", "end_date", "count", "message", "created_at"]])
            con.execute(
                """
                INSERT INTO dq_findings(finding_id, run_id, kind, severity, market, ticker, start_date, end_date, count, message, created_at)
                SELECT finding_id, run_id, kind, severity, market, ticker, start_date, end_date, count, message, created_at
                FROM df_findings
                """
            )

        # metrics (daily)
        metrics_rows = [
            ("ALL", "tickers", float(len(tm))),
            ("ALL", "missing_tickers", float(missing_tickers)),
            ("ALL", "stale_tickers", float(stale_tickers)),
            ("ALL", "invalid_rows", float(invalid_rows)),
            ("ALL", "findings", float(len(findings))),
            ("ALL", "duration_ms", float(t_ms())),
        ]

        # Per-market cheap rollups (tickers + findings)
        try:
            tm2 = tm.copy()
            tm2["market"] = tm2["market"].astype(str).str.strip().str.upper()
            for mkt, g in tm2.groupby("market"):
                metrics_rows.append((str(mkt), "tickers", float(len(g))))
        except Exception:
            pass

        if findings:
            try:
                fdf = pd.DataFrame(findings)
                if not fdf.empty and "market" in fdf.columns:
                    fdf["market"] = fdf["market"].astype(str).str.strip().str.upper()
                    for mkt, g in fdf.groupby("market"):
                        metrics_rows.append((str(mkt), "findings", float(len(g))))
            except Exception:
                pass

        # idempotent upsert per run
        try:
            con.execute("DELETE FROM dq_metrics_daily WHERE run_id = ?", [run_id])
        except Exception:
            pass

        mdf = pd.DataFrame(metrics_rows, columns=["market", "metric", "value"])
        mdf["run_id"] = run_id
        mdf["asof_date"] = asof_date
        mdf["created_at"] = datetime.now(timezone.utc)

        con.register(
            "df_metrics",
            mdf[["run_id", "asof_date", "market", "metric", "value", "created_at"]],
        )
        con.execute(
            '''
            INSERT INTO dq_metrics_daily(run_id, asof_date, market, metric, value, created_at)
            SELECT run_id, asof_date, market, metric, value, created_at
            FROM df_metrics
            '''
        )

        msg = f"dq_prices: run_id={run_id} asof={asof_date} missing_tickers={missing_tickers} stale_tickers={stale_tickers} invalid_rows={invalid_rows} findings={len(findings)}"
        return DqResult(status, msg, missing_tickers, invalid_rows, stale_tickers)
