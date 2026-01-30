from __future__ import annotations

"""Multi-source price backfill (audit-grade).

Goal
----
If the local DuckDB `prices` table has gaps or ends before a trade's intended exit,
SENTINEL-ALPHA should *attempt* to fill missing prices from alternative sources
*before* falling back to forced exits (last available price).

Design principles
-----------------
- Optional: can be disabled via configuration/env.
- Bounded: strict timeouts and max fetch windows.
- Auditable: every attempt is recorded in DuckDB `data_gaps`.
- Non-destructive: writes only to DuckDB (no CSV outputs).

Supported providers (best-effort)
--------------------------------
- yfinance (already a dependency)
- stooq (free CSV endpoint; parsed in-memory; stored in DuckDB)
- alpha_vantage (optional; requires ALPHAVANTAGE_API_KEY)

Important
---------
Different providers can disagree slightly. In this baseline we accept the
*latest fetched* value per (date, ticker) and record provenance columns.
"""

import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

import duckdb
import pandas as pd

# Optional deps
try:  # pragma: no cover
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

try:  # pragma: no cover
    import requests
except Exception:  # pragma: no cover
    requests = None


class PriceProvider(Protocol):
    name: str

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Return a DF with columns: date, price, open_price."""


@dataclass(frozen=True)
class BackfillResult:
    provider: str
    inserted_rows: int
    status: str
    message: str


class YFinanceProvider:
    name = "yfinance"

    def __init__(self, timeout_s: int = 20):
        self.timeout_s = int(timeout_s)

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if yf is None:
            return pd.DataFrame()

        # yfinance 'end' is exclusive; include end by adding one day
        end_plus = pd.Timestamp(end) + pd.Timedelta(days=1)
        try:
            df = yf.download(
                symbol,
                start=start,
                end=end_plus.date(),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as e:
            raise RuntimeError(f"YFINANCE_ERROR: {e}") from e

        if df is None or df.empty:
            return pd.DataFrame()

        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df.index, errors="coerce").normalize(),
                "open_price": pd.to_numeric(df.get("Open"), errors="coerce"),
                "price": pd.to_numeric(df.get("Close"), errors="coerce"),
            }
        ).dropna(subset=["date", "price"])

        out["date"] = out["date"].dt.date
        return out


class StooqProvider:
    name = "stooq"

    def __init__(self, timeout_s: int = 15):
        self.timeout_s = int(timeout_s)

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if requests is None:
            return pd.DataFrame()

        # Stooq daily endpoint returns the full history for the symbol.
        # We fetch and then slice in-memory (bounded by timeout).
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        try:
            resp = requests.get(url, timeout=self.timeout_s, headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            raise RuntimeError(f"NETWORK_ERROR: {e}") from e

        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")


        try:
            from io import StringIO

            df = pd.read_csv(StringIO(resp.text))
        except Exception as e:
            raise RuntimeError(f"PARSE_ERROR: {e}") from e

        if df is None or df.empty or "Date" not in df.columns:
            return pd.DataFrame()

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
        df = df.dropna(subset=["Date"])
        df = df[(df["Date"] >= start) & (df["Date"] <= end)]
        if df.empty:
            return pd.DataFrame()

        out = pd.DataFrame(
            {
                "date": df["Date"],
                "open_price": pd.to_numeric(df.get("Open"), errors="coerce"),
                "price": pd.to_numeric(df.get("Close"), errors="coerce"),
            }
        ).dropna(subset=["date", "price"])
        return out


class AlphaVantageProvider:
    name = "alpha_vantage"

    # Very conservative process-wide limiter (AlphaVantage free tier is typically ~5 req/min).
    _last_call_ts: float = 0.0

    def __init__(self, api_key: str, timeout_s: int = 20):
        self.api_key = api_key
        self.timeout_s = int(timeout_s)
        # Cache controls (file cache to avoid repeated pulls for the same symbol)
        self.cache_dir = os.environ.get("SENTINEL_AV_CACHE_DIR", os.path.join("data", "cache", "alphavantage")).strip()
        try:
            self.cache_ttl_s = int(os.environ.get("SENTINEL_AV_CACHE_TTL_SECONDS", "86400").strip())
        except Exception:
            self.cache_ttl_s = 86400
        # Rate limiting (min interval between calls)
        try:
            self.min_interval_s = float(os.environ.get("SENTINEL_AV_MIN_INTERVAL_S", "15").strip())
        except Exception:
            self.min_interval_s = 15.0
        # Retry/backoff
        try:
            self.max_retries = int(os.environ.get("SENTINEL_AV_MAX_RETRIES", "3").strip())
        except Exception:
            self.max_retries = 3

    def _cache_path(self, symbol: str) -> str:
        safe = symbol.replace("/", "_").replace("\\", "_")
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _read_cache(self, symbol: str) -> dict | None:
        p = self._cache_path(symbol)
        try:
            st = os.stat(p)
            if self.cache_ttl_s > 0 and (time.time() - st.st_mtime) > self.cache_ttl_s:
                return None
            import json

            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, symbol: str, payload: dict) -> None:
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            import json

            with open(self._cache_path(symbol), "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            return

    def _rate_limit(self) -> None:
        # Global per-process limiter.
        now = time.time()
        wait = (self.min_interval_s or 0.0) - (now - AlphaVantageProvider._last_call_ts)
        if wait > 0:
            time.sleep(wait)
        AlphaVantageProvider._last_call_ts = time.time()

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        if requests is None or not self.api_key:
            return pd.DataFrame()

        # Try file cache first.
        js = self._read_cache(symbol)

        # TIME_SERIES_DAILY_ADJUSTED is widely available but rate-limited.
        url = (
            "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED"
            f"&symbol={symbol}&outputsize=full&apikey={self.api_key}"
        )

        if js is None:
            # Network fetch with retry/backoff.
            backoff = 2.0
            for attempt in range(max(1, self.max_retries)):
                try:
                    self._rate_limit()
                    resp = requests.get(url, timeout=self.timeout_s, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}")
                    js = resp.json()

                    # AlphaVantage uses 'Note' or 'Information' when rate-limited.
                    if isinstance(js, dict) and ("Note" in js or "Information" in js):
                        raise RuntimeError("RATE_LIMIT")

                    if isinstance(js, dict) and js:
                        self._write_cache(symbol, js)
                    break
                except Exception:
                    js = None
                    if attempt >= max(1, self.max_retries) - 1:
                        break
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 30.0)

        if not js or not isinstance(js, dict):
            return pd.DataFrame()

        ts = js.get("Time Series (Daily)") or js.get("Time Series (Daily)") or js.get("Time Series (Daily) ")
        if not ts or not isinstance(ts, dict):
            return pd.DataFrame()

        rows = []
        for k, v in ts.items():
            try:
                d = pd.to_datetime(k).date()
            except Exception:
                continue
            if d < start or d > end:
                continue
            try:
                # Prefer adjusted close when present.
                close = float(v.get("5. adjusted close") or v.get("4. close") or v.get("4. close"))
                open_ = float(v.get("1. open")) if v.get("1. open") is not None else None
            except Exception:
                continue
            rows.append((d, open_, close))

        if not rows:
            return pd.DataFrame()

        out = pd.DataFrame(rows, columns=["date", "open_price", "price"]).dropna(subset=["date", "price"])
        return out


class PriceBackfiller:
    def __init__(
        self,
        con: duckdb.DuckDBPyConnection,
        providers: list[PriceProvider] | None = None,
        max_window_days: int = 120,
        write_audit_log: bool = True,
        run_id: str | None = None,
    ):
        self.con = con
        self.max_window_days = int(max_window_days)
        self.write_audit_log = bool(write_audit_log)
        self.run_id = (str(run_id).strip() if run_id else None)

        def _env_int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)).strip())
            except Exception:
                return default

        def _env_float(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, str(default)).strip())
            except Exception:
                return default

        # A5.1: operational hardening (no economic logic changes)
        self.http_timeout_s = max(1, _env_int("SENTINEL_HTTP_TIMEOUT_S", 20))
        self.fetch_max_retries = max(1, _env_int("SENTINEL_FETCH_MAX_RETRIES", 2))
        self.backoff_base_s = max(0.0, _env_float("SENTINEL_FETCH_BACKOFF_BASE_S", 1.0))
        self.backoff_max_s = max(0.1, _env_float("SENTINEL_FETCH_BACKOFF_MAX_S", 8.0))
        self.dedup_requests = os.environ.get("SENTINEL_DEDUP_BACKFILL_REQUESTS", "1").strip() not in {"0", "false", "FALSE", "no", "NO"}
        self._fetch_cache: dict[tuple, tuple[pd.DataFrame, str | None, int]] = {}
        self._upserted_keys: set[tuple] = set()

        if providers is not None:
            self.providers = providers
        else:
            # Provider order can be overridden for reproducibility and to deal with
            # regional/provider-specific outages.
            # Example: SENTINEL_PRICE_PROVIDER_ORDER="stooq,yfinance"
            order = [p.strip().lower() for p in os.environ.get("SENTINEL_PRICE_PROVIDER_ORDER", "yfinance,stooq").split(",")]

            disable_yf = os.environ.get("SENTINEL_DISABLE_YFINANCE", "").strip() in {"1", "true", "TRUE", "yes", "YES"}
            av_key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()

            providers_map: dict[str, PriceProvider] = {
                "yfinance": YFinanceProvider(timeout_s=self.http_timeout_s),
                "stooq": StooqProvider(timeout_s=self.http_timeout_s),
            }
            if av_key:
                av = AlphaVantageProvider(av_key, timeout_s=self.http_timeout_s)
                providers_map["alpha_vantage"] = av
                providers_map["alphavantage"] = av

            p: list[PriceProvider] = []
            for name in order:
                if name == "yfinance" and disable_yf:
                    continue
                prov = providers_map.get(name)
                if prov is not None:
                    p.append(prov)

            # Fallback to a sane default if the env var was empty/invalid.
            if not p:
                p = [StooqProvider()] if disable_yf else [YFinanceProvider(), StooqProvider()]

            self.providers = p

        # Provider health in the current process: if a provider returns empty
        # results repeatedly (common when blocked), disable it for the rest of
        # the run to avoid wasting time.
        self._fail_streak: dict[str, int] = {}
        self._disabled: set[str] = set()
        self._disable_after = int(os.environ.get("SENTINEL_PROVIDER_DISABLE_AFTER", "3"))


    def _log(
        self,
        kind: str,
        ticker: str,
        start: date,
        end: date,
        status: str,
        provider: str,
        message: str,
        *,
        reason_code: str | None = None,
        requested_start: date | None = None,
        requested_end: date | None = None,
        obtained_start: date | None = None,
        obtained_end: date | None = None,
        rows_inserted: int | None = None,
        rows_upserted: int | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if not self.write_audit_log:
            return
        try:
            cols = getattr(self, "_data_gaps_cols", None)
            if cols is None:
                try:
                    cols = {r[1] for r in self.con.execute("PRAGMA table_info('data_gaps')").fetchall()}
                except Exception:
                    cols = set()
                self._data_gaps_cols = cols

            fields: list[str] = [
                "run_id",
                "kind",
                "ticker",
                "start_date",
                "end_date",
                "requested_at",
                "status",
                "provider",
                "message",
            ]
            values: list = [
                self.run_id,
                kind,
                ticker,
                start,
                end,
                datetime.now(timezone.utc),
                status,
                provider,
                (message or "")[:500],
            ]

            # Optional standardized classification and richer range provenance
            if "reason_code" in cols:
                fields.append("reason_code")
                values.append((reason_code or "")[:64] if reason_code else None)

            if "requested_start_date" in cols:
                fields.append("requested_start_date")
                values.append(requested_start)
            if "requested_end_date" in cols:
                fields.append("requested_end_date")
                values.append(requested_end)

            if "obtained_start_date" in cols:
                fields.append("obtained_start_date")
                values.append(obtained_start)
            if "obtained_end_date" in cols:
                fields.append("obtained_end_date")
                values.append(obtained_end)

            if "rows_inserted" in cols:
                fields.append("rows_inserted")
                values.append(rows_inserted)

            if "rows_upserted" in cols:
                fields.append("rows_upserted")
                values.append(rows_upserted)

            if "error" in cols:
                fields.append("error")
                values.append((error[:500] if error else None))

            if "duration_ms" in cols:
                fields.append("duration_ms")
                values.append(duration_ms)

            ph = ", ".join(["?"] * len(fields))
            sql = f"INSERT INTO data_gaps({', '.join(fields)}) VALUES ({ph})"
            self.con.execute(sql, values)
        except Exception:
            # Logging must never break the pipeline.
            return

    @staticmethod
    def _classify_failure_reason(error: str | None, message: str | None = None) -> str:
        e = (error or "").upper()
        m = (message or "").upper()

        if "PARSE_ERROR" in e or "JSONDECODE" in e or "PARSERERROR" in e:
            return "PARSE_ERROR"

        if "RATE_LIMIT" in e or "RATE_LIMIT" in m or "HTTP 429" in e or " 429" in e:
            return "RATE_LIMIT"
        if "HTTP 403" in e or "HTTP 401" in e or "403" in e or "401" in e or "BLOCK" in e:
            return "BLOCKED"
        if any(
            s in e
            for s in [
                "HTTPSCONNECTIONPOOL",
                "CONNECTIONERROR",
                "CONNECTION ABORTED",
                "CONNECTION RESET",
                "TIMEOUT",
                "TIMED OUT",
                "TEMPORARY FAILURE",
                "NAME OR SERVICE NOT KNOWN",
                "DNS",
                "MAX RETRIES",
            ]
        ):
            return "NETWORK_ERROR"
        return "EMPTY_PROVIDER"

    def _resolve_symbol(self, ticker: str, provider_name: str) -> str:
        """Resolve a provider-specific symbol using metadata, with conservative fallbacks."""

        t = str(ticker).strip().upper()
        try:
            row = self.con.execute(
                "SELECT yf_symbol, stooq_symbol, market FROM metadata WHERE ticker = ?",
                [t],
            ).fetchone()
        except Exception:
            row = None

        yf_sym = row[0] if row else None
        stq_sym = row[1] if row else None
        market = (row[2] if row else None) or ("EU" if "." in t else "US")

        if provider_name == "yfinance":
            return str(yf_sym).strip() if yf_sym else t

        if provider_name == "stooq":
            if stq_sym:
                return str(stq_sym).strip().lower()
            # Common default for US tickers on Stooq: aapl.us
            if market.upper() == "US" and "." not in t:
                return f"{t.lower()}.us"
            # Otherwise best-effort
            return t.lower()

        # Alpha Vantage generally uses standard US-style symbols
        return t

    def _backoff_seconds(self, attempt: int) -> float:
        # Deterministic exponential backoff (no jitter) to keep certify reproducible.
        try:
            return min(self.backoff_max_s, self.backoff_base_s * (2.0 ** max(0, int(attempt))))
        except Exception:
            return min(8.0, 1.0 * (2.0 ** max(0, int(attempt))))

    def _fetch_with_retry(self, prov: PriceProvider, symbol: str, start: date, end: date) -> tuple[pd.DataFrame, str | None, int, int, bool]:
        """Fetch with retry/backoff and in-run dedup for (provider, symbol, range).

        Returns: (df, err, duration_ms, attempts_used, cached)
        """

        key = (prov.name, str(symbol), start, end)
        if self.dedup_requests and key in self._fetch_cache:
            c_df, c_err, c_ms = self._fetch_cache[key]
            return c_df.copy(), c_err, int(c_ms), 0, True

        # Avoid double-retry: AlphaVantage already has internal retry/backoff.
        max_tries = 1 if isinstance(prov, AlphaVantageProvider) else int(self.fetch_max_retries)
        max_tries = max(1, max_tries)

        df = pd.DataFrame()
        err: str | None = None
        t0 = time.perf_counter()
        for attempt in range(max_tries):
            try:
                df = prov.fetch(symbol, start, end)
                err = None
            except Exception as e:
                err = str(e)
                df = pd.DataFrame()

            if df is not None and not df.empty:
                break

            if attempt < max_tries - 1:
                time.sleep(self._backoff_seconds(attempt))

        dt_ms = int((time.perf_counter() - t0) * 1000)

        if self.dedup_requests:
            try:
                self._fetch_cache[key] = (df.copy() if df is not None else pd.DataFrame(), err, dt_ms)
            except Exception:
                self._fetch_cache[key] = (pd.DataFrame(), err, dt_ms)

        return df, err, dt_ms, max_tries, False

    def backfill_prices(self, ticker: str, start: date, end: date) -> list[BackfillResult]:
        """Try multiple providers and upsert into DuckDB.

        The end date is clamped to `max_window_days` from start.
        """

        start_d = pd.to_datetime(start).date()
        end_d = pd.to_datetime(end).date()
        if end_d < start_d:
            start_d, end_d = end_d, start_d

        requested_start_d = start_d
        requested_end_d = end_d

        # OFFLINE guard (defensive).
        # If the process is configured to run offline, or online backfill is explicitly
        # disabled, we must not attempt any *network* calls (requests/yfinance/etc).
        #
        # However, unit tests and some internal flows inject offline-safe providers
        # (e.g., a fake provider) that do not touch the network. In those cases we
        # should still allow the injected providers to run even when the process is
        # in OFFLINE mode.
        truthy = {"1", "true", "yes", "y", "on"}
        offline = os.environ.get("SENTINEL_OFFLINE", "").strip().lower() in truthy
        allow_raw = os.environ.get("SENTINEL_ALLOW_ONLINE_BACKFILL", "").strip().lower()
        allow_online = True if not allow_raw else (allow_raw in truthy)

        network_providers = {"yfinance", "stooq", "alpha_vantage", "alphavantage"}
        providers = self.providers

        if offline or not allow_online:
            # Keep only offline-safe providers (i.e., not known network providers).
            safe = [p for p in self.providers if str(getattr(p, "name", "")).strip().lower() not in network_providers]
            if not safe:
                msg = "online price backfill skipped (OFFLINE guard)"
                self._log(
                    "prices",
                    str(ticker).strip().upper(),
                    start_d,
                    end_d,
                    "SKIPPED",
                    "system",
                    msg,
                    reason_code="OFFLINE",
                    requested_start=requested_start_d,
                    requested_end=requested_end_d,
                )
                return []
            providers = safe

        # Do not request future data. Providers will either return empty or,
        # worse, behave inconsistently. We clamp to today's date.
        today = date.today()
        if start_d > today:
            msg = f"start_date {start_d} is after today {today}; skipping backfill"
            self._log("prices", str(ticker).strip().upper(), start_d, start_d, "SKIPPED", "system", msg, reason_code="OUT_OF_RANGE", requested_start=requested_start_d, requested_end=requested_end_d)
            return []

        # Clamp window (start + max_window_days) and clamp to today.
        max_end = (pd.Timestamp(start_d) + pd.Timedelta(days=self.max_window_days)).date()
        effective_end = min(end_d, max_end, today)
        if effective_end < start_d:
            msg = f"effective_end {effective_end} < start_date {start_d}; skipping backfill"
            self._log("prices", str(ticker).strip().upper(), start_d, effective_end, "SKIPPED", "system", msg, reason_code="OUT_OF_RANGE", requested_start=requested_start_d, requested_end=requested_end_d)
            return []

        results: list[BackfillResult] = []

        for prov in providers:
            if prov.name in self._disabled:
                msg = f"provider disabled after {self._fail_streak.get(prov.name, 0)} consecutive failures"
                self._log("prices", str(ticker).strip().upper(), start_d, effective_end, "SKIPPED", prov.name, msg, reason_code="BLOCKED", requested_start=requested_start_d, requested_end=requested_end_d)
                results.append(BackfillResult(prov.name, 0, "SKIPPED", msg))
                continue

            sym = self._resolve_symbol(ticker, prov.name)
            df, err, dt_ms, attempts_used, cached = self._fetch_with_retry(prov, sym, start_d, effective_end)

            if df is None or df.empty:
                extra = f"attempts={attempts_used}" + ("; cached" if cached else "")
                msg = f"no data returned for symbol={sym} ({extra})"
                reason = self._classify_failure_reason(err, msg)
                self._log(
                    "prices",
                    str(ticker).strip().upper(),
                    start_d,
                    effective_end,
                    "FAILED",
                    prov.name,
                    msg,
                    reason_code=reason,
                    requested_start=requested_start_d,
                    requested_end=requested_end_d,
                    rows_inserted=0,
                    rows_upserted=0,
                    error=err,
                    duration_ms=dt_ms,
                )
                results.append(BackfillResult(prov.name, 0, "FAILED", msg))

                if not cached:
                    self._fail_streak[prov.name] = int(self._fail_streak.get(prov.name, 0)) + 1
                    if self._fail_streak[prov.name] >= self._disable_after:
                        self._disabled.add(prov.name)
                continue

            df = df.copy()
            df["ticker"] = str(ticker).strip().upper()
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
            df["price"] = pd.to_numeric(df["price"], errors="coerce")
            df["open_price"] = pd.to_numeric(df.get("open_price"), errors="coerce")
            df = df.dropna(subset=["date", "ticker", "price"])
            if df.empty:
                msg = f"parsed empty after cleaning for symbol={sym}"
                self._log(
                    "prices",
                    str(ticker).strip().upper(),
                    start_d,
                    effective_end,
                    "FAILED",
                    prov.name,
                    msg,
                    reason_code="PARSE_ERROR",
                    requested_start=requested_start_d,
                    requested_end=requested_end_d,
                    rows_inserted=0,
                    rows_upserted=0,
                    error=err,
                    duration_ms=dt_ms,
                )
                results.append(BackfillResult(prov.name, 0, "FAILED", msg))

                self._fail_streak[prov.name] = int(self._fail_streak.get(prov.name, 0)) + 1
                if self._fail_streak[prov.name] >= self._disable_after:
                    self._disabled.add(prov.name)
                continue

            obtained_start: date | None = None
            obtained_end: date | None = None
            try:
                obtained_start = pd.to_datetime(df["date"].min(), errors="coerce").date()  # type: ignore[attr-defined]
                obtained_end = pd.to_datetime(df["date"].max(), errors="coerce").date()  # type: ignore[attr-defined]
            except Exception:
                obtained_start = None
                obtained_end = None

            upsert_key = (prov.name, str(sym), start_d, effective_end)
            if self.dedup_requests and upsert_key in self._upserted_keys:
                msg = "dedup: already upserted provider+symbol+range in this run"
                self._log(
                    "prices",
                    str(ticker).strip().upper(),
                    start_d,
                    effective_end,
                    "SKIPPED",
                    prov.name,
                    msg,
                    reason_code="SUCCESS_NO_NEW_ROWS",
                    requested_start=requested_start_d,
                    requested_end=requested_end_d,
                    obtained_start=obtained_start,
                    obtained_end=obtained_end,
                    rows_inserted=0,
                    rows_upserted=0,
                    error=None,
                    duration_ms=0,
                )
                results.append(BackfillResult(prov.name, 0, "SKIPPED", msg))
                break

            df["source"] = prov.name
            df["fetched_at"] = pd.Timestamp.utcnow().to_pydatetime()

            self.con.register("df_backfill", df[["date", "ticker", "price", "open_price", "source", "fetched_at"]])
            try:
                # Measure "new" rows inserted (not updates) for audit.
                before = int(
                    self.con.execute(
                        "SELECT COUNT(*) FROM prices WHERE ticker = ? AND date BETWEEN ? AND ?",
                        [df["ticker"].iloc[0], start_d, effective_end],
                    ).fetchone()[0]
                )

                self.con.execute(
                    """
                    INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
                    SELECT date, ticker, price, open_price, source, fetched_at FROM df_backfill
                    ON CONFLICT(date, ticker)
                    DO UPDATE SET
                      price=excluded.price,
                      open_price=excluded.open_price,
                      source=excluded.source,
                      fetched_at=excluded.fetched_at
                    """
                )
                after = int(
                    self.con.execute(
                        "SELECT COUNT(*) FROM prices WHERE ticker = ? AND date BETWEEN ? AND ?",
                        [df["ticker"].iloc[0], start_d, effective_end],
                    ).fetchone()[0]
                )
                inserted_new = max(0, after - before)
                upserted = int(len(df))
                msg = f"upserted={upserted} (new={inserted_new}) rows from symbol={sym}"
                reason = "SUCCESS_NEW_ROWS" if int(inserted_new or 0) > 0 else "SUCCESS_NO_NEW_ROWS"
                self._log(
                    "prices",
                    str(ticker).strip().upper(),
                    start_d,
                    effective_end,
                    "SUCCESS",
                    prov.name,
                    msg,
                    reason_code=reason,
                    requested_start=requested_start_d,
                    requested_end=requested_end_d,
                    obtained_start=obtained_start,
                    obtained_end=obtained_end,
                    rows_inserted=inserted_new,
                    rows_upserted=upserted,
                    error=None,
                    duration_ms=dt_ms,
                )
                results.append(BackfillResult(prov.name, upserted, "SUCCESS", msg))

                try:
                    self._upserted_keys.add(upsert_key)
                except Exception:
                    pass

                # Success resets fail streak.
                self._fail_streak[prov.name] = 0

                # Stop at the first successful provider by default.
                break
            except Exception as e:
                msg = f"duckdb upsert failed: {e}"
                self._log(
                    "prices",
                    str(ticker).strip().upper(),
                    start_d,
                    effective_end,
                    "FAILED",
                    prov.name,
                    msg,
                    reason_code="PARSE_ERROR",
                    requested_start=requested_start_d,
                    requested_end=requested_end_d,
                    rows_inserted=0,
                    rows_upserted=0,
                    error=str(e),
                    duration_ms=dt_ms,
                )
                results.append(BackfillResult(prov.name, 0, "FAILED", msg))

                self._fail_streak[prov.name] = int(self._fail_streak.get(prov.name, 0)) + 1
                if self._fail_streak[prov.name] >= self._disable_after:
                    self._disabled.add(prov.name)

        return results
