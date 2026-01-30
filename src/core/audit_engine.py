from __future__ import annotations

import os
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from src.db.migrate import ensure_schema
from src.core.cost_model import CostModel
from src.core.tax_model import ItalianTaxModel
from src.core.ticker_normalize import normalize_ticker_sql
from src.data.price_backfill import PriceBackfiller


def _safe_bool(value, default: bool = False) -> bool:
    """Coerce a value to bool, treating Pandas missing values (pd.NA/NaN) as default.

    Prevents: `TypeError: boolean value of NA is ambiguous`.
    """
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        # Some non-scalar types may not be supported by pd.isna
        pass
    try:
        return bool(value)
    except Exception:
        return default


def _safe_float(value, default: float) -> float:
    """Coerce a value to float, treating Pandas missing values (pd.NA/NaN) as default."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest configuration for the audit engine."""

    starting_capital: float = 100000.0
    holding_period_sessions: int = 22

    # Risk-based sizing (conservative defaults)
    risk_per_trade: float = 0.01
    max_position_pct: float = 0.20
    max_positions: int = 10
    cash_reserve_pct: float = 0.20

    # Costs
    include_costs: bool = True
    round_trip_cost_pct: float = 0.0075

    # Taxes (Italian resident)
    include_taxes: bool = True
    capital_gains_rate: float = 0.26

    # Retail realism (execution feasibility)
    # - whole_shares: enforce integer shares (default True for retail brokers)
    # - min_trade_notional: skip micro-trades that are not economically feasible
    # - include_dividends: apply cash dividends from `dividends` table as portfolio cashflows (Policy B)
    # - dividend_withholding_rate: optional withholding (0..1), applied to gross dividends at payment
    whole_shares: bool = True
    min_trade_notional: float = 250.0
    include_dividends: bool = False
    dividend_withholding_rate: float = 0.0

    # Optional online backfill (multi-source) to reduce forced exits caused by missing forward prices.
    # For certification workflows, you may disable this and rely on a frozen local dataset.
    allow_online_backfill: bool = False
    backfill_window_days: int = 90


class AuditEngine:
    def __init__(self, db_path: str | None = None, con: duckdb.DuckDBPyConnection | None = None):
        self.db_path = db_path or os.path.join("data", "sentinel_alpha.db")
        self.con = con or duckdb.connect(database=self.db_path)
        ensure_schema(self.con)

        # Introspection for reporting / certification.
        self.last_audit_stats: dict[str, float | int | str] = {}
        self.last_realized_trades: pd.DataFrame | None = None
        self.last_trade_ledger_raw: pd.DataFrame | None = None

    def close(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass

    def verify_signal_price_coverage(self, universe_id: str = "ALL", sample_limit: int = 20) -> dict:
        """Pre-audit gate: validate that eligible signals reference tickers with price coverage.

        Rationale
        ---------
        Retail providers (yfinance/stooq) and corporate actions can introduce symbol drift (e.g., mergers,
        re-tickerings, punctuation differences). The audit engine already maps tickers via `ticker_mappings`
        and filters out signals that cannot be entered (no next trading session). However, silently dropping
        such signals can mask data quality issues and "sporcarsi" the audit.

        This gate computes coverage *after* survivorship and ticker-mapping eligibility, and returns:
        - signals/tickers with *no* price series in `prices` (hard integrity failure)
        - signals/tickers that are right-censored (ticker has prices, but no session strictly after the signal)

        The caller can decide whether to fail fast or warn-only (via env knobs).
        """
        sample_limit = max(0, int(sample_limit))

        # Conservative ticker canonicalization (DOT for class shares).
        r_base = "upper(trim(r.ticker))"
        r_norm = normalize_ticker_sql("r.ticker")
        um_norm = normalize_ticker_sql("um.ticker")
        tmr_alias_norm = normalize_ticker_sql("tmr.alias_ticker")
        tmr_can_norm = normalize_ticker_sql("tmr.canonical_ticker")
        tmu_alias_norm = normalize_ticker_sql("tmu.alias_ticker")
        tmu_can_norm = normalize_ticker_sql("tmu.canonical_ticker")

        sql_base = f"""
        WITH recs_mapped AS (
            SELECT
                r.date AS signal_date,
                r.ticker AS ticker_original,
                {r_norm} AS ticker_normalized,
                COALESCE({tmr_can_norm}, {r_norm}) AS ticker,
                CASE WHEN ({r_base} != r.ticker OR {r_norm} != {r_base}) THEN 1 ELSE 0 END AS normalization_changed,
                CASE WHEN tmr.canonical_ticker IS NOT NULL THEN 1 ELSE 0 END AS mapping_applied,
                r.firm,
                r.rating,
                r.sentiment_score,
                r.universe_id
            FROM recs r
            LEFT JOIN ticker_mappings tmr
              ON {tmr_alias_norm} = {r_norm}
             AND (tmr.start_date IS NULL OR r.date >= tmr.start_date)
             AND (tmr.end_date IS NULL OR r.date <= tmr.end_date)
        ),
        eligible AS (
            SELECT rm.*
            FROM recs_mapped rm
            JOIN universe_membership um
              ON um.universe_id = ?
             AND (um.start_date IS NULL OR rm.signal_date >= um.start_date)
             AND (um.end_date IS NULL OR rm.signal_date <= um.end_date)
            LEFT JOIN ticker_mappings tmu
              ON {tmu_alias_norm} = {um_norm}
             AND (tmu.start_date IS NULL OR rm.signal_date >= tmu.start_date)
             AND (tmu.end_date IS NULL OR rm.signal_date <= tmu.end_date)
            WHERE COALESCE({tmu_can_norm}, {um_norm}) = rm.ticker
        ),
        price_stats AS (
            SELECT
                ticker,
                MIN(date) AS first_price_date,
                MAX(date) AS last_price_date,
                COUNT(*) AS n_prices
            FROM prices
            GROUP BY ticker
        ),
        elig_prices AS (
            SELECT
                e.signal_date,
                e.ticker,
                e.ticker_original,
                e.ticker_normalized,
                e.normalization_changed,
                e.mapping_applied,
                e.firm,
                e.rating,
                e.sentiment_score,
                ps.n_prices,
                ps.first_price_date,
                ps.last_price_date,
                (SELECT MIN(p.date) FROM prices p WHERE p.ticker = e.ticker AND p.date > e.signal_date) AS intended_buy_date
            FROM eligible e
            LEFT JOIN price_stats ps ON ps.ticker = e.ticker
        )
        """

        stats = self.con.execute(
            sql_base
            + """
            SELECT
                COUNT(*) AS eligible_signals,
                SUM(CASE WHEN n_prices IS NULL THEN 1 ELSE 0 END) AS signals_missing_price_series,
                COUNT(DISTINCT CASE WHEN n_prices IS NULL THEN ticker END) AS tickers_missing_price_series,
                SUM(CASE WHEN n_prices IS NOT NULL AND intended_buy_date IS NULL THEN 1 ELSE 0 END) AS signals_right_censored,
                COUNT(DISTINCT CASE WHEN n_prices IS NOT NULL AND intended_buy_date IS NULL THEN ticker END) AS tickers_right_censored,
                SUM(normalization_changed) AS signals_normalization_changed,
                COUNT(DISTINCT CASE WHEN normalization_changed = 1 THEN ticker_normalized END) AS tickers_normalization_changed,
                SUM(mapping_applied) AS signals_mapping_applied,
                COUNT(DISTINCT CASE WHEN mapping_applied = 1 THEN ticker_normalized END) AS tickers_mapping_applied,
                COUNT(DISTINCT ticker_original) AS tickers_original_distinct,
                COUNT(DISTINCT ticker) AS tickers_effective_distinct
            FROM elig_prices
            """,
            [universe_id],
        ).fetchone()

        eligible_signals = int(stats[0] or 0)
        missing_signals = int(stats[1] or 0)
        missing_tickers = int(stats[2] or 0)
        rc_signals = int(stats[3] or 0)
        rc_tickers = int(stats[4] or 0)
        norm_signals = int(stats[5] or 0)
        norm_tickers = int(stats[6] or 0)
        mapped_signals = int(stats[7] or 0)
        mapped_tickers = int(stats[8] or 0)
        distinct_original = int(stats[9] or 0)
        distinct_effective = int(stats[10] or 0)

        out = {
            "universe_id": universe_id,
            "eligible_signals": eligible_signals,
            "signals_missing_price_series": missing_signals,
            "tickers_missing_price_series": missing_tickers,
            "signals_right_censored": rc_signals,
            "tickers_right_censored": rc_tickers,
            "signals_normalization_changed": norm_signals,
            "tickers_normalization_changed": norm_tickers,
            "signals_mapping_applied": mapped_signals,
            "tickers_mapping_applied": mapped_tickers,
            "tickers_original_distinct": distinct_original,
            "tickers_effective_distinct": distinct_effective,
            "missing_price_series_sample": [],
            "right_censored_sample": [],
            "mapping_change_sample": [],
        }

        if eligible_signals > 0:
            out["pct_missing_price_series_signals"] = float(missing_signals) / float(eligible_signals)
            out["pct_right_censored_signals"] = float(rc_signals) / float(eligible_signals)
        else:
            out["pct_missing_price_series_signals"] = 0.0
            out["pct_right_censored_signals"] = 0.0

        # Samples (bounded).
        if sample_limit > 0 and missing_signals > 0:
            miss = self.con.execute(
                sql_base
                + """
                SELECT
                    ticker,
                    COUNT(*) AS signals,
                    MIN(signal_date) AS first_signal_date,
                    MAX(signal_date) AS last_signal_date
                FROM elig_prices
                WHERE n_prices IS NULL
                GROUP BY ticker
                ORDER BY signals DESC, ticker ASC
                LIMIT ?
                """,
                [universe_id, sample_limit],
            ).df()
            out["missing_price_series_sample"] = miss.to_dict(orient="records")

        if sample_limit > 0 and rc_signals > 0:
            rc = self.con.execute(
                sql_base
                + """
                SELECT
                    ticker,
                    COUNT(*) AS signals,
                    MAX(last_price_date) AS last_price_date,
                    MIN(signal_date) AS first_signal_date,
                    MAX(signal_date) AS last_signal_date
                FROM elig_prices
                WHERE n_prices IS NOT NULL AND intended_buy_date IS NULL
                GROUP BY ticker
                ORDER BY signals DESC, ticker ASC
                LIMIT ?
                """,
                [universe_id, sample_limit],
            ).df()
            out["right_censored_sample"] = rc.to_dict(orient="records")

        if sample_limit > 0 and (norm_signals > 0 or mapped_signals > 0):
            mc = self.con.execute(
                sql_base
                + """
                SELECT
                    ticker_original,
                    ticker_normalized,
                    ticker AS ticker_effective,
                    SUM(normalization_changed) AS normalized_signals,
                    SUM(mapping_applied) AS mapped_signals,
                    COUNT(*) AS signals
                FROM elig_prices
                WHERE normalization_changed = 1 OR mapping_applied = 1
                GROUP BY ticker_original, ticker_normalized, ticker
                ORDER BY signals DESC, ticker_effective ASC
                LIMIT ?
                """,
                [universe_id, sample_limit],
            ).df()
            out["mapping_change_sample"] = mc.to_dict(orient="records")

        # Publish to stats for reporting.
        self.last_audit_stats = dict(self.last_audit_stats or {})
        self.last_audit_stats.update(
            {
                "gate_input_eligible_signals": eligible_signals,
                "gate_input_missing_price_series_signals": missing_signals,
                "gate_input_missing_price_series_tickers": missing_tickers,
                "gate_input_right_censored_signals": rc_signals,
                "gate_input_right_censored_tickers": rc_tickers,
                "gate_input_signals_normalization_changed": norm_signals,
                "gate_input_tickers_normalization_changed": norm_tickers,
                "gate_input_signals_mapping_applied": mapped_signals,
                "gate_input_tickers_mapping_applied": mapped_tickers,
                "gate_input_tickers_effective_distinct": distinct_effective,
            }
        )
        return out



    def backfill_prices_for_forced_exits(
        self,
        trades: pd.DataFrame,
        cfg: BacktestConfig,
        providers: list | None = None,
        run_id: str | None = None,
    ) -> dict:
        """Attempt multi-source price backfill for trades that required a forced exit.

        This does *not* guarantee the gap can be filled (providers can fail), but it
        ensures we try before accepting the fallback.

        Returns a small stats dict suitable for embedding in the audit report.
        """

        stats = {
            "backfill_enabled": bool(cfg.allow_online_backfill),
            "backfill_forced_exits": 0,
            "backfill_attempts": 0,
            "backfill_rows_upserted": 0,
            "backfill_success": 0,
        }

        if trades is None or trades.empty:
            return stats

        if not cfg.allow_online_backfill:
            return stats

        forced = (
            trades.loc[trades["exit_reason"] == "FALLBACK_LAST_PRICE"].copy()
            if (hasattr(trades, "columns") and "exit_reason" in trades.columns)
            else trades.loc[trades.get("exit_is_fallback", False) == True].copy()
        )
        if forced.empty:
            return stats

        stats["backfill_forced_exits"] = int(len(forced))

        # Attach run_id for audit-grade provenance (data_gaps).
        run_id = (run_id or os.environ.get("SENTINEL_RUN_ID") or "").strip() or None
        backfiller = PriceBackfiller(
            self.con,
            providers=providers,
            max_window_days=int(cfg.backfill_window_days),
            run_id=run_id,
        )

        # Deduplicate attempts: per (ticker, buy_date) is sufficient.
        forced = forced.drop_duplicates(subset=["ticker", "buy_date"]).reset_index(drop=True)

        for _, row in forced.iterrows():
            try:
                tkr = str(row["ticker"]).strip().upper()
                bd = pd.to_datetime(row["buy_date"], errors="coerce")
                if pd.isna(bd):
                    continue
                start = bd.date()
                # Never request future data (providers will return empty and waste time).
                today = pd.Timestamp.utcnow().date()
                end = min((bd + pd.Timedelta(days=int(cfg.backfill_window_days))).date(), today)
                if end < start:
                    continue

                stats["backfill_attempts"] += 1
                res = backfiller.backfill_prices(tkr, start=start, end=end)
                if not res:
                    continue

                # Consider success if any provider upserted >0 rows
                upserted = sum(int(r.inserted_rows) for r in res)
                stats["backfill_rows_upserted"] += upserted
                if any(r.status == "SUCCESS" and r.inserted_rows > 0 for r in res):
                    stats["backfill_success"] += 1
            except Exception:
                continue

        return stats

    def run_trade_audit(self, universe_id: str = "ALL", cfg: BacktestConfig | None = None) -> pd.DataFrame:
        """Build a trade ledger with conservative time alignment and institutional gates.

        Guarantees
        ----------
        - **Survivorship control**: a signal is eligible only if the (mapped) ticker is a member of
          `universe_membership` on the signal date.
        - **Ticker mapping**: time-bounded mappings (`ticker_mappings`) are applied to both `recs.ticker`
          and `universe_membership.ticker` to handle symbol changes/corporate actions.
        - **No look-ahead**: entry is the next trading session strictly after the signal date.
        - **Execution feasibility**: optional `ticker_halts` and `market_halts` can shift entry/exit to the
          first feasible session; if shifting exceeds configured limits, the trade is skipped.
        - **Exit**: `holding_period_sessions` sessions after entry; if insufficient forward prices, exit
          falls back to the last available session (flagged).

        Returns a DataFrame with per-trade gross and net returns.
        """

        cfg = cfg or BacktestConfig()
        hp = int(cfg.holding_period_sessions)
        if hp < 1:
            raise ValueError("holding_period_sessions must be >= 1")

        # ------------------------------------------------------------------
        # Pre-audit input gate: signal tickers must have price coverage.
        # ------------------------------------------------------------------
        gate_enabled = _safe_bool(os.environ.get("SENTINEL_GATE_VERIFY_INPUTS", "1"), default=True)
        if gate_enabled:
            sample_limit = int(os.environ.get("SENTINEL_GATE_SAMPLE_LIMIT", "20") or 20)
            coverage = self.verify_signal_price_coverage(universe_id=universe_id, sample_limit=sample_limit)
            fail_on_missing = _safe_bool(
                os.environ.get("SENTINEL_GATE_FAIL_ON_MISSING_PRICE_SERIES", "1"),
                default=True,
            )
            if fail_on_missing and int(coverage.get("signals_missing_price_series", 0) or 0) > 0:
                # Fail-fast with a compact, operator-friendly message.
                sample = coverage.get("missing_price_series_sample", []) or []
                head = ", ".join([str(r.get("ticker")) for r in sample[:10]]) if sample else ""
                raise RuntimeError(
                    "GATE FAIL: eligible signals reference tickers without any price series in `prices` "
                    f"(signals_missing_price_series={coverage.get('signals_missing_price_series')}, "
                    f"tickers_missing_price_series={coverage.get('tickers_missing_price_series')}). "
                    + (f"Sample tickers: {head}." if head else "")
                )

        # Shift limits (sessions) for halt-aware execution.
        def _env_int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)).strip())
            except Exception:
                return default

        max_entry_shift = max(0, _env_int("SENTINEL_MAX_ENTRY_SHIFT_SESSIONS", 5))
        max_exit_shift = max(0, _env_int("SENTINEL_MAX_EXIT_SHIFT_SESSIONS", 10))

        # Default Italian FTT/Tobin rate for instruments flagged in metadata (fraction of notional).
        try:
            default_ftt_rate = float(os.environ.get("SENTINEL_DEFAULT_FTT_RATE", "0.001").strip())
        except Exception:
            default_ftt_rate = 0.001
        default_ftt_rate = max(0.0, default_ftt_rate)

        # ------------------------------------------------------------------
        # Load halts into memory for fast checks (optional tables).
        # ------------------------------------------------------------------
        def _load_ticker_halts() -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
            try:
                h = self.con.execute(
                    """
                    SELECT ticker, start_date, COALESCE(end_date, DATE '9999-12-31') AS end_date, COALESCE(reason,'')
                    FROM ticker_halts
                    """
                ).df()
            except Exception:
                return {}
            if h.empty:
                return {}
            h["start_date"] = pd.to_datetime(h["start_date"]).dt.normalize()
            h["end_date"] = pd.to_datetime(h["end_date"]).dt.normalize()
            out: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]] = {}
            for r in h.itertuples(index=False):
                out.setdefault(str(r.ticker).upper(), []).append((r.start_date, r.end_date, str(r.reason)))
            return out

        def _load_market_halts() -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]]:
            try:
                h = self.con.execute(
                    """
                    SELECT market, start_date, COALESCE(end_date, DATE '9999-12-31') AS end_date, COALESCE(reason,'')
                    FROM market_halts
                    """
                ).df()
            except Exception:
                return {}
            if h.empty:
                return {}
            h["start_date"] = pd.to_datetime(h["start_date"]).dt.normalize()
            h["end_date"] = pd.to_datetime(h["end_date"]).dt.normalize()
            out: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, str]]] = {}
            for r in h.itertuples(index=False):
                out.setdefault(str(r.market).upper(), []).append((r.start_date, r.end_date, str(r.reason)))
            return out

        ticker_halts = _load_ticker_halts()
        market_halts = _load_market_halts()

        def _halt_reason(ticker: str, market: str | None, d: pd.Timestamp) -> str | None:
            t = str(ticker).upper()
            m = str(market).upper() if market else ""
            for (s, e, reason) in ticker_halts.get(t, []):
                if s <= d <= e:
                    return f"TICKER_HALT:{reason}" if reason else "TICKER_HALT"
            if m:
                for (s, e, reason) in market_halts.get(m, []):
                    if s <= d <= e:
                        return f"MARKET_HALT:{reason}" if reason else "MARKET_HALT"
            return None

        # ------------------------------------------------------------------
        # Eligibility + intended entry (SQL): survivorship + ticker mapping.
        # ------------------------------------------------------------------
        # Notes:
        # - We map both recs.ticker and universe_membership.ticker to canonical tickers.
        # - We compute intended_buy_date from prices of canonical ticker.
        r_norm = normalize_ticker_sql("r.ticker")
        um_norm = normalize_ticker_sql("um.ticker")
        tmr_alias_norm = normalize_ticker_sql("tmr.alias_ticker")
        tmr_can_norm = normalize_ticker_sql("tmr.canonical_ticker")
        tmu_alias_norm = normalize_ticker_sql("tmu.alias_ticker")
        tmu_can_norm = normalize_ticker_sql("tmu.canonical_ticker")
        query = f"""
        WITH recs_mapped AS (
            SELECT
                r.date AS signal_date,
                r.ticker AS ticker_original,
                {r_norm} AS ticker_normalized,
                COALESCE({tmr_can_norm}, {r_norm}) AS ticker,
                r.firm,
                r.rating,
                r.sentiment_score,
                r.universe_id
            FROM recs r
            LEFT JOIN ticker_mappings tmr
              ON {tmr_alias_norm} = {r_norm}
             AND (tmr.start_date IS NULL OR r.date >= tmr.start_date)
             AND (tmr.end_date IS NULL OR r.date <= tmr.end_date)
        ),
        eligible AS (
            SELECT rm.*
            FROM recs_mapped rm
            JOIN universe_membership um
              ON um.universe_id = ?
             AND (um.start_date IS NULL OR rm.signal_date >= um.start_date)
             AND (um.end_date IS NULL OR rm.signal_date <= um.end_date)
            LEFT JOIN ticker_mappings tmu
              ON {tmu_alias_norm} = {um_norm}
             AND (tmu.start_date IS NULL OR rm.signal_date >= tmu.start_date)
             AND (tmu.end_date IS NULL OR rm.signal_date <= tmu.end_date)
            WHERE COALESCE({tmu_can_norm}, {um_norm}) = rm.ticker
        ),
        base AS (
            SELECT
                e.signal_date,
                e.ticker,
                e.ticker_original,
                e.firm,
                e.rating,
                e.sentiment_score,
                COALESCE(m.market, u.market) AS market,
                m.sector,
                m.instrument_type,
                m.is_tobin_tax,
                m.ftt_rate,
                u.universe_id,
                (SELECT MIN(p.date) FROM prices p WHERE p.ticker = e.ticker AND p.date > e.signal_date) AS intended_buy_date
            FROM eligible e
            LEFT JOIN metadata m ON m.ticker = e.ticker
            LEFT JOIN universes u ON u.universe_id = ?
        )
        SELECT *
        FROM base
        WHERE intended_buy_date IS NOT NULL
        ORDER BY intended_buy_date ASC, ticker ASC
        """

        base = self.con.execute(query, [universe_id, universe_id]).df()
        self.last_trade_ledger_raw = base.copy()

        if base.empty:
            self.last_audit_stats = {
                "universe_id": universe_id,
                "eligible_signals": 0,
                "eligible_trades_dedup": 0,
                "dedup_dropped": 0,
                "forced_exits": 0,
                "skipped": 0,
                "entry_shifted": 0,
                "exit_shifted": 0,
            }
            return base

        # ------------------------------------------------------------------
        # Preload price calendars for involved tickers (authoritative).
        # ------------------------------------------------------------------
        tickers = sorted(set(base["ticker"].astype(str).str.upper().tolist()))
        # Load all dates for these tickers (minimize per-row SQL).
        px_dates = self.con.execute(
            """
            SELECT ticker, date
            FROM prices
            WHERE ticker IN (SELECT * FROM UNNEST(?))
            ORDER BY ticker, date
            """,
            [tickers],
        ).df()
        px_dates["date"] = pd.to_datetime(px_dates["date"]).dt.normalize()
        cal: dict[str, list[pd.Timestamp]] = {}
        for tkr, g in px_dates.groupby("ticker"):
            cal[str(tkr).upper()] = list(g["date"].tolist())

        # Helper: fetch execution price for a given (ticker,date).
        def _price_at(ticker: str, d: pd.Timestamp, which: str) -> float | None:
            # which: 'buy' -> open/close; 'sell' -> close
            try:
                if which == "buy":
                    row = self.con.execute(
                        "SELECT COALESCE(open_price, price) FROM prices WHERE ticker=? AND date=?",
                        [ticker, d.date()],
                    ).fetchone()
                else:
                    row = self.con.execute(
                        "SELECT price FROM prices WHERE ticker=? AND date=?",
                        [ticker, d.date()],
                    ).fetchone()
                if not row:
                    return None
                v = row[0]
                return None if v is None else float(v)
            except Exception:
                return None

        # Helper: shift date forward until not halted (or fail).
        def _shift_date(ticker: str, market: str | None, intended: pd.Timestamp, limit: int) -> tuple[pd.Timestamp | None, int, str | None]:
            dates = cal.get(str(ticker).upper(), [])
            if not dates:
                return None, 0, "NO_PRICE_CALENDAR"

            # find first calendar index >= intended
            i = 0
            # binary search
            lo, hi = 0, len(dates)
            while lo < hi:
                mid = (lo + hi) // 2
                if dates[mid] < intended:
                    lo = mid + 1
                else:
                    hi = mid
            i = lo
            shift = 0
            first_reason = None
            while i < len(dates):
                d = dates[i]
                reason = _halt_reason(ticker, market, d)
                if reason is None:
                    return d, shift, first_reason
                if first_reason is None:
                    first_reason = reason
                if shift >= limit:
                    return None, shift, first_reason
                i += 1
                shift += 1
            return None, shift, first_reason

        # ------------------------------------------------------------------
        # Build executed trades (and optional decision ledger).
        # ------------------------------------------------------------------
        rows = []
        decisions = []
        raw_signals = int(len(base))

        run_id = (os.environ.get("SENTINEL_RUN_ID") or "").strip() or None

        for r in base.itertuples(index=False):
            ticker = str(r.ticker).upper()
            market = str(r.market).upper() if getattr(r, "market", None) else None
            signal_date = pd.to_datetime(r.signal_date).normalize()
            intended_buy_date = pd.to_datetime(r.intended_buy_date).normalize()

            buy_date, entry_shift, entry_halt = _shift_date(ticker, market, intended_buy_date, max_entry_shift)
            if buy_date is None:
                # skipped
                decisions.append(
                    {
                        "run_id": run_id,
                        "signal_date": signal_date.date(),
                        "ticker_original": getattr(r, "ticker_original", None),
                        "ticker": ticker,
                        "firm": r.firm,
                        "rating": r.rating,
                        "universe_id": universe_id,
                        "intended_buy_date": intended_buy_date.date(),
                        "buy_date": None,
                        "exec_shift_sessions": int(entry_shift),
                        "intended_sell_date": None,
                        "sell_date": None,
                        "exit_shift_sessions": None,
                        "decision": "SKIPPED",
                        "skip_reason": "ENTRY_SHIFT_EXCEEDED" if entry_halt else "NO_ENTRY_DATE",
                        "halt_reason": entry_halt,
                    }
                )
                continue

            buy_price = _price_at(ticker, buy_date, which="buy")
            if buy_price is None:
                decisions.append(
                    {
                        "run_id": run_id,
                        "signal_date": signal_date.date(),
                        "ticker_original": getattr(r, "ticker_original", None),
                        "ticker": ticker,
                        "firm": r.firm,
                        "rating": r.rating,
                        "universe_id": universe_id,
                        "intended_buy_date": intended_buy_date.date(),
                        "buy_date": buy_date.date(),
                        "exec_shift_sessions": int(entry_shift),
                        "decision": "SKIPPED",
                        "skip_reason": "MISSING_BUY_PRICE",
                        "halt_reason": entry_halt,
                    }
                )
                continue

            # Determine intended exit based on *actual* entry date.
            dates = cal.get(ticker, [])
            try:
                entry_idx = dates.index(buy_date)
            except ValueError:
                entry_idx = None

            raw_sell_date = None
            exit_is_fallback = False
            end_of_data_mark_to_market = False
            if entry_idx is not None:
                target_idx = entry_idx + hp
                if target_idx < len(dates):
                    raw_sell_date = dates[target_idx]
                else:
                    # End-of-sample right-censoring: we cannot realize the full holding period.
                    # We mark-to-market at the last available session (audit-visible).
                    raw_sell_date = dates[-1] if dates else None
                    exit_is_fallback = True
                    end_of_data_mark_to_market = True
            else:
                raw_sell_date = dates[-1] if dates else None
                exit_is_fallback = True

            if raw_sell_date is None:
                decisions.append(
                    {
                        "run_id": run_id,
                        "signal_date": signal_date.date(),
                        "ticker_original": getattr(r, "ticker_original", None),
                        "ticker": ticker,
                        "firm": r.firm,
                        "rating": r.rating,
                        "universe_id": universe_id,
                        "intended_buy_date": intended_buy_date.date(),
                        "buy_date": buy_date.date(),
                        "exec_shift_sessions": int(entry_shift),
                        "decision": "SKIPPED",
                        "skip_reason": "NO_EXIT_DATE",
                        "halt_reason": entry_halt,
                    }
                )
                continue

            sell_date, exit_shift, exit_halt = _shift_date(ticker, market, raw_sell_date, max_exit_shift)
            if sell_date is None:
                decisions.append(
                    {
                        "run_id": run_id,
                        "signal_date": signal_date.date(),
                        "ticker_original": getattr(r, "ticker_original", None),
                        "ticker": ticker,
                        "firm": r.firm,
                        "rating": r.rating,
                        "universe_id": universe_id,
                        "intended_buy_date": intended_buy_date.date(),
                        "buy_date": buy_date.date(),
                        "exec_shift_sessions": int(entry_shift),
                        "intended_sell_date": raw_sell_date.date() if raw_sell_date is not None else None,
                        "sell_date": None,
                        "exit_shift_sessions": int(exit_shift),
                        "decision": "SKIPPED",
                        "skip_reason": "EXIT_SHIFT_EXCEEDED",
                        "halt_reason": exit_halt or entry_halt,
                    }
                )
                continue

            sell_price = _price_at(ticker, sell_date, which="sell")
            if sell_price is None:
                decisions.append(
                    {
                        "run_id": run_id,
                        "signal_date": signal_date.date(),
                        "ticker_original": getattr(r, "ticker_original", None),
                        "ticker": ticker,
                        "firm": r.firm,
                        "rating": r.rating,
                        "universe_id": universe_id,
                        "intended_buy_date": intended_buy_date.date(),
                        "buy_date": buy_date.date(),
                        "exec_shift_sessions": int(entry_shift),
                        "intended_sell_date": raw_sell_date.date() if raw_sell_date is not None else None,
                        "sell_date": sell_date.date(),
                        "exit_shift_sessions": int(exit_shift),
                        "decision": "SKIPPED",
                        "skip_reason": "MISSING_SELL_PRICE",
                        "halt_reason": exit_halt or entry_halt,
                    }
                )
                continue

            # Momentum regime from monthly ranking, latest before entry
            try:
                mom = self.con.execute(
                    "SELECT signal FROM momentum_rankings WHERE ticker=? AND date < ? ORDER BY date DESC LIMIT 1",
                    [ticker, buy_date.date()],
                ).fetchone()
                mom_status = mom[0] if mom else None
            except Exception:
                mom_status = None

            # Risk proxy: stdev of daily log returns over last 30 trading sessions before entry
            try:
                rv = self.con.execute(
                    """
                    SELECT STDDEV(lr) * 100
                    FROM (
                        SELECT LN(price / LAG(price) OVER (ORDER BY date)) AS lr
                        FROM prices
                        WHERE ticker=? AND date < ?
                        ORDER BY date DESC
                        LIMIT 31
                    )
                    WHERE lr IS NOT NULL
                    """,
                    [ticker, buy_date.date()],
                ).fetchone()
                risk_vol = float(rv[0]) if rv and rv[0] is not None else None
            except Exception:
                risk_vol = None

            gross_return_pct = round((sell_price - buy_price) / buy_price * 100.0, 4) if buy_price else None

            halt_reason = exit_halt or entry_halt

            rows.append(
                {
                    "signal_date": signal_date.date(),
                    "buy_date": buy_date.date(),
                    "sell_date": sell_date.date(),
                    "exit_is_fallback": bool(exit_is_fallback),
                    "exit_reason": (
                        "MARK_TO_MARKET_END_OF_DATA"
                        if end_of_data_mark_to_market
                        else (
                            "FALLBACK_LAST_PRICE"
                            if exit_is_fallback
                            else ("HALT_SHIFT" if exit_shift > 0 else "HOLDING_PERIOD")
                        )
                    ),
                    "ticker": ticker,
                    "ticker_original": getattr(r, "ticker_original", None),
                    "firm": r.firm,
                    "rating": r.rating,
                    "market": getattr(r, "market", None),
                    "sector": getattr(r, "sector", None),
                    "instrument_type": getattr(r, "instrument_type", None),
                    "mom_status": mom_status,
                    "risk_vol": risk_vol,
                    "is_tobin_tax": _safe_bool(getattr(r, "is_tobin_tax", False), default=False),
                    "sentiment_score": getattr(r, "sentiment_score", None),
                    "buy_price": float(buy_price),
                    "sell_price": float(sell_price),
                    "universe_id": universe_id,
                    "gross_return_pct": gross_return_pct,
                    "exec_shift_sessions": int(entry_shift),
                    "exit_shift_sessions": int(exit_shift),
                    "halt_reason": halt_reason,
                    "ftt_rate": _safe_float(getattr(r, "ftt_rate", None), default_ftt_rate) if _safe_bool(getattr(r, "is_tobin_tax", False), default=False) else 0.0,
                }
            )

            decisions.append(
                {
                    "run_id": run_id,
                    "signal_date": signal_date.date(),
                    "ticker_original": getattr(r, "ticker_original", None),
                    "ticker": ticker,
                    "firm": r.firm,
                    "rating": r.rating,
                    "universe_id": universe_id,
                    "intended_buy_date": intended_buy_date.date(),
                    "buy_date": buy_date.date(),
                    "exec_shift_sessions": int(entry_shift),
                    "intended_sell_date": raw_sell_date.date() if raw_sell_date is not None else None,
                    "sell_date": sell_date.date(),
                    "exit_shift_sessions": int(exit_shift),
                    "decision": "EXECUTED",
                    "skip_reason": None,
                    "halt_reason": halt_reason,
                }
            )

        df = pd.DataFrame(rows)

        if df.empty:
            self.last_audit_stats = {
                "universe_id": universe_id,
                "eligible_signals": raw_signals,
                "eligible_trades_dedup": 0,
                "dedup_dropped": 0,
                "forced_exits": 0,
                "skipped": raw_signals,
                "entry_shifted": 0,
                "exit_shifted": 0,
            }
            # Best-effort persist decisions
            self._persist_decisions(decisions, run_id=run_id)
            return df

        # --- Deterministic scoring (used for dedup and portfolio selection) ---
        def _rating_score(rating: str | None) -> float:
            if rating is None:
                return 0.0
            x = str(rating).strip().lower()
            if "downgrad" in x:
                return -1.0
            if "upgrad" in x:
                return 2.0
            if "initi" in x:
                return 1.5
            if "buy" in x or "overweight" in x or "outperform" in x:
                return 1.25
            if "hold" in x or "neutral" in x:
                return 0.25
            return 0.5

        def _mom_score(m: str | None) -> float:
            if m is None:
                return 0.0
            x = str(m).strip().upper()
            if x == "BEST":
                return 0.5
            if x == "WORST":
                return -0.5
            return 0.0

        df["trade_score"] = (
            df["rating"].apply(_rating_score)
            + df["mom_status"].apply(_mom_score)
            + pd.to_numeric(df.get("sentiment_score", 0.0), errors="coerce").fillna(0.0).astype(float) * 0.25
        )

        # --- Dedup policy: one executed trade per ticker per entry date ---
        df = df.sort_values(["buy_date", "trade_score", "firm"], ascending=[True, False, True])
        before = len(df)
        df = df.drop_duplicates(subset=["ticker", "buy_date"], keep="first").reset_index(drop=True)
        dropped = before - len(df)

        # Mark dropped decisions (best-effort)
        if dropped > 0 and decisions:
            kept_keys = {(r["ticker"], r["buy_date"]) for r in df[["ticker", "buy_date"]].to_dict("records")}
            for d in decisions:
                if d.get("decision") == "EXECUTED" and d.get("buy_date") is not None:
                    k = (str(d.get("ticker")).upper(), pd.to_datetime(d.get("buy_date")).date())
                    if k not in kept_keys:
                        d["decision"] = "DROPPED_DEDUP"
                        d["skip_reason"] = "DEDUP"

        # Costs
        cost_model = CostModel(round_trip_cost_pct=cfg.round_trip_cost_pct)
        if cfg.include_costs:
            df["cost_pct"] = cost_model.cost_pct() * 100.0
            df["net_return_pct"] = df["gross_return_pct"].apply(cost_model.apply_to_return_pct)
        else:
            df["cost_pct"] = 0.0
            df["net_return_pct"] = df["gross_return_pct"].astype(float)

        # FTT/Tobin (entry-side) as a separate penalty.
        df["ftt_pct"] = (pd.to_numeric(df.get("ftt_rate", 0.0), errors="coerce").fillna(0.0).astype(float) * 100.0)
        df["net_return_pct"] = df["net_return_pct"] - df["ftt_pct"]

        # Stats for the report
        forced_total = int(df["exit_is_fallback"].sum()) if "exit_is_fallback" in df.columns else 0
        fallback_exits = int((df["exit_reason"] == "FALLBACK_LAST_PRICE").sum()) if "exit_reason" in df.columns else 0
        mark_to_market_exits = int((df["exit_reason"] == "MARK_TO_MARKET_END_OF_DATA").sum()) if "exit_reason" in df.columns else 0

        self.last_audit_stats = {
            "universe_id": universe_id,
            "eligible_signals": raw_signals,
            "eligible_trades_dedup": int(len(df)),
            "dedup_dropped": int(dropped),
            # Backward-compatible aggregate: any exit that did not realize the intended holding period.
            "forced_exits": int(forced_total),
            "forced_exits_total": int(forced_total),
            # Breakdown for audit/reporting.
            "fallback_exits": int(fallback_exits),
            "mark_to_market_exits": int(mark_to_market_exits),
            "skipped": int(sum(1 for d in decisions if d.get("decision") == "SKIPPED")),
            "entry_shifted": int((pd.to_numeric(df.get("exec_shift_sessions", 0), errors="coerce").fillna(0) > 0).sum()),
            "exit_shifted": int((pd.to_numeric(df.get("exit_shift_sessions", 0), errors="coerce").fillna(0) > 0).sum()),
        }

        # Best-effort persist decisions to DuckDB.
        self._persist_decisions(decisions, run_id=run_id)

        return df

    def _persist_decisions(self, decisions: list[dict], run_id: str | None) -> None:
        """Persist the decision ledger (best-effort, idempotent-ish).

        This is intentionally non-blocking: certification should not fail because a
        logging table is missing.
        """

        if not run_id:
            return
        if not decisions:
            return
        try:
            ensure_schema(self.con)
        except Exception:
            return

        try:
            import hashlib
            from datetime import datetime, timezone

            rows = []
            now = datetime.now(timezone.utc)
            for d in decisions:
                # Stable-ish id for the decision row.
                key = f"{run_id}|{d.get('signal_date')}|{d.get('ticker_original')}|{d.get('ticker')}|{d.get('firm')}|{d.get('rating')}|{d.get('intended_buy_date')}"
                decision_id = hashlib.sha1(key.encode('utf-8')).hexdigest()
                rows.append(
                    {
                        "decision_id": decision_id,
                        "run_id": run_id,
                        "signal_date": d.get("signal_date"),
                        "ticker_original": d.get("ticker_original"),
                        "ticker": d.get("ticker"),
                        "firm": d.get("firm"),
                        "rating": d.get("rating"),
                        "universe_id": d.get("universe_id"),
                        "intended_buy_date": d.get("intended_buy_date"),
                        "buy_date": d.get("buy_date"),
                        "exec_shift_sessions": d.get("exec_shift_sessions"),
                        "intended_sell_date": d.get("intended_sell_date"),
                        "sell_date": d.get("sell_date"),
                        "exit_shift_sessions": d.get("exit_shift_sessions"),
                        "decision": d.get("decision"),
                        "skip_reason": d.get("skip_reason"),
                        "halt_reason": d.get("halt_reason"),
                        "created_at": now,
                    }
                )

            df = pd.DataFrame(rows)
            if df.empty:
                return

            self.con.register("df_audit_signal_decisions", df)
            # Insert explicitly by columns (robust against schema ordering).
            cols = [
                "decision_id",
                "run_id",
                "signal_date",
                "ticker_original",
                "ticker",
                "firm",
                "rating",
                "universe_id",
                "intended_buy_date",
                "buy_date",
                "exec_shift_sessions",
                "intended_sell_date",
                "sell_date",
                "exit_shift_sessions",
                "decision",
                "skip_reason",
                "halt_reason",
                "created_at",
            ]
            col_list = ",".join(cols)
            self.con.execute(f"INSERT INTO audit_signal_decisions({col_list}) SELECT {col_list} FROM df_audit_signal_decisions ON CONFLICT(decision_id) DO NOTHING")
            self.con.unregister("df_audit_signal_decisions")
        except Exception:
            try:
                self.con.unregister("df_audit_signal_decisions")
            except Exception:
                pass
            return




    def simulate_portfolio(self, trades: pd.DataFrame, cfg: BacktestConfig | None = None) -> pd.DataFrame:
        """Event-driven portfolio simulation with overlapping positions.

        Conservative retail-grade assumptions:
        - No leverage.
        - Maintain a cash reserve.
        - Volatility-aware sizing with max-position cap.
        - One position per ticker.
        - Optional whole-shares execution (integer shares).
        - Optional minimum trade notional (skip micro-trades).
        - Optional cash-dividend modeling (Policy B: unadjusted prices + cashflows).

        Taxes (Italian CGT) are applied on realized PnL at exit when enabled.
        """

        cfg = cfg or BacktestConfig()
        self.last_realized_trades = None

        # --- Retail realism knobs ---
        whole_shares = bool(getattr(cfg, "whole_shares", True))
        min_trade_notional = float(getattr(cfg, "min_trade_notional", 0.0) or 0.0)
        include_dividends = bool(getattr(cfg, "include_dividends", False))
        wht = float(getattr(cfg, "dividend_withholding_rate", 0.0) or 0.0)
        if wht < 0.0:
            wht = 0.0
        if wht > 1.0:
            wht = 1.0

        # --- Stats for reporting ---
        skipped_zero_shares = 0
        skipped_min_notional = 0
        skipped_insufficient_cash = 0
        skipped_duplicate_ticker = 0
        skipped_buy_price_invalid = 0
        skipped_capacity = 0

        dividend_entitlements = 0
        dividend_payments = 0
        dividend_gross_paid = 0.0
        dividend_net_paid = 0.0
        dividend_rows_skipped_currency = 0

        if trades is None or trades.empty:
            # Still publish knobs for audit traceability
            if isinstance(getattr(self, "last_audit_stats", None), dict):
                self.last_audit_stats.update(
                    {
                        "portfolio_whole_shares": whole_shares,
                        "portfolio_min_trade_notional": min_trade_notional,
                        "portfolio_include_dividends": include_dividends,
                        "portfolio_dividend_withholding_rate": wht,
                    }
                )
            return pd.DataFrame(
                columns=[
                    "date",
                    "equity",
                    "cash",
                    "open_positions",
                    "tax_paid",
                    "executed_trades",
                    "closed_trades",
                    "dividends_paid",
                    "dividends_gross_paid",
                    "dividends_events",
                ]
            )

        t = trades.copy()
        t["buy_date"] = pd.to_datetime(t.get("buy_date"), errors="coerce").dt.normalize()
        t["sell_date"] = pd.to_datetime(t.get("sell_date"), errors="coerce").dt.normalize()

        # Require prices for a serious, mark-to-market simulation.
        required = ["ticker", "buy_date", "sell_date", "buy_price", "sell_price"]
        miss = [c for c in required if c not in t.columns]
        if miss:
            raise ValueError(f"simulate_portfolio requires columns: {miss}")

        # Drop trades that still have missing critical fields.
        t = t.dropna(subset=["ticker", "buy_date", "sell_date", "buy_price", "sell_price"]).copy()
        if t.empty:
            if isinstance(getattr(self, "last_audit_stats", None), dict):
                self.last_audit_stats.update(
                    {
                        "portfolio_whole_shares": whole_shares,
                        "portfolio_min_trade_notional": min_trade_notional,
                        "portfolio_include_dividends": include_dividends,
                        "portfolio_dividend_withholding_rate": wht,
                    }
                )
            return pd.DataFrame(
                columns=[
                    "date",
                    "equity",
                    "cash",
                    "open_positions",
                    "tax_paid",
                    "executed_trades",
                    "closed_trades",
                    "dividends_paid",
                    "dividends_gross_paid",
                    "dividends_events",
                ]
            )

        t["risk_vol"] = t.get("risk_vol", 0.0).astype(float).fillna(0.0)
        t["trade_score"] = t.get("trade_score", 0.0).astype(float).fillna(0.0)
        if "firm" not in t.columns:
            t["firm"] = ""
        else:
            t["firm"] = t["firm"].astype(str).fillna("")

        # Deterministic intra-day ordering: higher score first.
        t = t.sort_values(["buy_date", "trade_score", "ticker", "firm"], ascending=[True, False, True, True]).reset_index(drop=True)

        start = t["buy_date"].min()
        end_trades = t["sell_date"].max()

        tickers = sorted(set(t["ticker"].astype(str).str.upper().tolist()))
        t["ticker"] = t["ticker"].astype(str).str.upper()

        # --- Dividends: preload and determine extended horizon (so pay_date after exits is captured) ---
        div_df = pd.DataFrame()
        if include_dividends and tickers:
            try:
                div_df = self.con.execute(
                    """
                    SELECT ticker, ex_date, pay_date, amount, currency
                    FROM dividends
                    WHERE ticker IN (SELECT * FROM UNNEST(?))
                      AND ex_date BETWEEN ? AND ?
                    """,
                    [tickers, start.date(), end_trades.date()],
                ).df()
            except Exception:
                div_df = pd.DataFrame()

        if not div_df.empty:
            div_df["ticker"] = div_df["ticker"].astype(str).str.upper()
            div_df["ex_date"] = pd.to_datetime(div_df["ex_date"], errors="coerce").dt.normalize()
            div_df["pay_date"] = pd.to_datetime(div_df["pay_date"], errors="coerce").dt.normalize()
            div_df["amount"] = pd.to_numeric(div_df["amount"], errors="coerce").fillna(0.0).astype(float)
            div_df = div_df.dropna(subset=["ticker", "ex_date", "pay_date"]).copy()
            div_df = div_df.loc[div_df["amount"] != 0.0].copy()

        end = end_trades
        if not div_df.empty:
            try:
                max_pay = div_df["pay_date"].max()
                if pd.notna(max_pay) and max_pay > end:
                    end = max_pay
            except Exception:
                pass

        # Trading-day calendar from the DB (authoritative)
        cal_rows = self.con.execute(
            "SELECT DISTINCT date FROM prices WHERE date BETWEEN ? AND ? ORDER BY date ASC",
            [start.date(), end.date()],
        ).fetchall()

        trading_days = pd.to_datetime([r[0] for r in cal_rows]).normalize() if cal_rows else pd.DatetimeIndex([])

        # Build dividend schedules (ex_date → rows, pay_date_adj → payments)
        dividends_by_ex = {}
        dividends_pay = {}
        if include_dividends and not div_df.empty:
            def _next_trading_day(d0: pd.Timestamp) -> pd.Timestamp:
                if trading_days is None or len(trading_days) == 0:
                    return d0
                idx = int(trading_days.searchsorted(d0, side="left"))
                if idx < len(trading_days):
                    return pd.Timestamp(trading_days[idx]).normalize()
                return d0

            div_df["pay_date_adj"] = div_df["pay_date"].apply(_next_trading_day)

            for _, r in div_df.iterrows():
                ccy = str(r.get("currency") or "").strip().upper()
                if ccy not in {"", "USD", "US$", "US DOLLAR"}:
                    dividend_rows_skipped_currency += 1
                    continue

                exd = pd.Timestamp(r["ex_date"]).normalize()
                payd = pd.Timestamp(r["pay_date_adj"]).normalize()
                dividends_by_ex.setdefault(exd, []).append(
                    {"ticker": str(r["ticker"]).upper(), "amount": float(r["amount"]), "pay_date": payd}
                )
                dividends_pay.setdefault(payd, [])

            try:
                max_pay_adj = div_df["pay_date_adj"].max()
                if pd.notna(max_pay_adj) and max_pay_adj > end:
                    end = max_pay_adj
            except Exception:
                pass

        event_dates = set(pd.to_datetime(t["buy_date"]).dt.normalize().tolist()) | set(pd.to_datetime(t["sell_date"]).dt.normalize().tolist())
        if include_dividends and dividends_pay:
            event_dates |= set(dividends_pay.keys())

        if trading_days is None or len(trading_days) == 0:
            calendar = pd.Index(sorted(event_dates))
        else:
            calendar = pd.Index(sorted(set(trading_days.tolist()) | event_dates))

        if len(calendar) == 0:
            return pd.DataFrame(
                columns=[
                    "date",
                    "equity",
                    "cash",
                    "open_positions",
                    "tax_paid",
                    "executed_trades",
                    "closed_trades",
                    "dividends_paid",
                    "dividends_gross_paid",
                    "dividends_events",
                ]
            )

        # Load prices for involved tickers and forward-fill within the calendar.
        px = self.con.execute(
            """
            SELECT date, ticker, price
            FROM prices
            WHERE date BETWEEN ? AND ?
              AND ticker IN (SELECT * FROM UNNEST(?))
            """,
            [start.date(), end.date(), tickers],
        ).df()

        if px.empty:
            raise RuntimeError("No prices found for the requested backtest window.")

        px["date"] = pd.to_datetime(px["date"]).dt.normalize()
        px["ticker"] = px["ticker"].astype(str).str.upper()
        px_pivot = (
            px.pivot_table(index="date", columns="ticker", values="price", aggfunc="last")
            .sort_index()
            .reindex(calendar)
            .ffill()
        )

        cash = float(cfg.starting_capital)
        reserve = float(cfg.cash_reserve_pct)
        max_pos = int(cfg.max_positions)
        risk_per_trade = float(cfg.risk_per_trade)
        max_pos_pct = float(cfg.max_position_pct)

        cost_model = CostModel(round_trip_cost_pct=cfg.round_trip_cost_pct) if cfg.include_costs else CostModel(round_trip_cost_pct=0.0)
        tax_model = ItalianTaxModel(capital_gains_rate=cfg.capital_gains_rate) if cfg.include_taxes else None

        open_pos: list[dict] = []
        open_tickers: set[str] = set()
        realized_rows: list[dict] = []
        equity_curve: list[dict] = []

        cumulative_tax = 0.0
        executed = 0
        closed = 0

        by_buy = {d: g for d, g in t.groupby("buy_date")}

        for d in calendar:
            d = pd.Timestamp(d).normalize()

            # 0) Pay dividends scheduled for today
            if include_dividends:
                due = dividends_pay.get(d, [])
                if due:
                    gross = float(sum(x["gross"] for x in due))
                    net = float(sum(x["net"] for x in due))
                    cash += net
                    dividend_gross_paid += gross
                    dividend_net_paid += net
                    dividend_payments += len(due)
                    dividends_pay[d] = []

            # 1) Close positions scheduled for today
            if open_pos:
                still_open = []
                for p in open_pos:
                    if p["sell_date"] != d:
                        still_open.append(p)
                        continue

                    exit_price = float(p["sell_price"])
                    exit_gross = float(p["shares"]) * exit_price
                    exit_cost = cost_model.exit_cost(exit_gross)
                    exit_proceeds = exit_gross - exit_cost
                    realized_pnl = exit_proceeds - p["entry_outflow"]

                    tax_paid = 0.0
                    if tax_model is not None:
                        after_tax_pnl, tax_paid = tax_model.apply_to_realized_pnl(realized_pnl)
                        if tax_paid:
                            cash -= tax_paid
                            cumulative_tax += tax_paid
                    else:
                        after_tax_pnl = realized_pnl

                    cash += exit_proceeds
                    closed += 1
                    open_tickers.discard(p["ticker"])

                    realized_rows.append(
                        {
                            "ticker": p["ticker"],
                            "buy_date": p["buy_date"],
                            "sell_date": p["sell_date"],
                            "notional": p["notional"],
                            "shares": p["shares"],
                            "buy_price": p["buy_price"],
                            "sell_price": exit_price,
                            "entry_cost": p["entry_cost"],
                            "ftt_cost": float(p.get("ftt_cost", 0.0)),
                            "exit_cost": exit_cost,
                            "realized_pnl": realized_pnl,
                            "tax_paid": tax_paid,
                            "after_tax_pnl": after_tax_pnl,
                            "after_tax_return_pct": (after_tax_pnl / p["notional"] * 100.0) if p["notional"] else 0.0,
                            "exit_is_fallback": bool(p.get("exit_is_fallback", False)),
                            "exit_reason": p.get("exit_reason", ""),
                        }
                    )

                open_pos = still_open

            # 1.5) Record dividend entitlements on ex-date
            if include_dividends and dividends_by_ex:
                ex_rows = dividends_by_ex.get(d)
                if ex_rows and open_pos:
                    for r in ex_rows:
                        tkr = r["ticker"]
                        amt = float(r["amount"])
                        payd = pd.Timestamp(r["pay_date"]).normalize()
                        for p in open_pos:
                            if p["ticker"] != tkr:
                                continue
                            if p["buy_date"] >= d:
                                continue
                            if p["sell_date"] <= d:
                                continue
                            gross = float(p["shares"]) * amt
                            if gross == 0.0:
                                continue
                            net = gross * (1.0 - wht)
                            dividends_pay.setdefault(payd, []).append({"ticker": tkr, "gross": gross, "net": net, "ex_date": d})
                            dividend_entitlements += 1

            # 2) Open new positions
            todays = by_buy.get(d)
            if todays is not None and not todays.empty:
                free_slots = max(0, max_pos - len(open_pos))
                if free_slots <= 0:
                    skipped_capacity += int(len(todays))
                else:
                    deployable = max(0.0, cash * (1.0 - reserve))
                    if deployable > 0:
                        cand = todays.copy()
                        dup_mask = cand["ticker"].isin(open_tickers)
                        if dup_mask.any():
                            skipped_duplicate_ticker += int(dup_mask.sum())
                        cand = cand.loc[~dup_mask].copy()

                        if len(cand) > free_slots:
                            skipped_capacity += int(len(cand) - free_slots)
                            cand = cand.head(free_slots)

                        prelim = []
                        for _, row in cand.iterrows():
                            vol = max(0.5, float(row.get("risk_vol", 0.0)))
                            target_risk_amt = cash * risk_per_trade
                            notional = target_risk_amt / (vol / 100.0)
                            notional = min(notional, cash * max_pos_pct)
                            notional = max(0.0, float(notional))

                            entry_cost = cost_model.entry_cost(notional)
                            ftt_rate = float(row.get("ftt_rate", 0.0) or 0.0)
                            if not ftt_rate:
                                try:
                                    ftt_rate = float(row.get("ftt_pct", 0.0) or 0.0) / 100.0
                                except Exception:
                                    ftt_rate = 0.0
                            ftt_cost = notional * ftt_rate
                            outflow = notional + entry_cost + ftt_cost
                            prelim.append((notional, ftt_rate, outflow))

                        total_out = float(sum(x[2] for x in prelim))
                        scale = 1.0
                        if total_out > deployable and total_out > 0:
                            scale = deployable / total_out

                        for (_, row), (notional, ftt_rate, _) in zip(cand.iterrows(), prelim):
                            desired = float(notional) * float(scale)
                            buy_price = float(row["buy_price"])
                            if buy_price <= 0:
                                skipped_buy_price_invalid += 1
                                continue

                            if whole_shares:
                                shares = int(desired / buy_price)
                                if shares <= 0:
                                    skipped_zero_shares += 1
                                    continue
                                notional_eff = float(shares) * buy_price
                            else:
                                shares = float(desired / buy_price) if buy_price else 0.0
                                if shares <= 0:
                                    skipped_zero_shares += 1
                                    continue
                                notional_eff = float(desired)

                            if min_trade_notional > 0 and notional_eff < min_trade_notional:
                                skipped_min_notional += 1
                                continue

                            entry_cost = cost_model.entry_cost(notional_eff)
                            ftt_cost = notional_eff * float(ftt_rate)
                            outflow = notional_eff + entry_cost + ftt_cost
                            if outflow <= 0 or outflow > cash:
                                skipped_insufficient_cash += 1
                                continue

                            cash -= outflow
                            executed += 1
                            pos = {
                                "ticker": str(row["ticker"]).upper(),
                                "buy_date": pd.Timestamp(row["buy_date"]).normalize(),
                                "sell_date": pd.Timestamp(row["sell_date"]).normalize(),
                                "notional": float(notional_eff),
                                "buy_price": buy_price,
                                "sell_price": float(row["sell_price"]),
                                "shares": float(shares) if not whole_shares else int(shares),
                                "entry_cost": float(entry_cost),
                                "ftt_cost": float(ftt_cost),
                                "entry_outflow": float(outflow),
                                "exit_is_fallback": bool(row.get("exit_is_fallback", False)),
                                "exit_reason": row.get("exit_reason", ""),
                            }

                            if pos["sell_date"] == d:
                                exit_price = float(pos["sell_price"])
                                exit_gross = float(pos["shares"]) * exit_price
                                exit_cost = cost_model.exit_cost(exit_gross)
                                exit_proceeds = exit_gross - exit_cost
                                realized_pnl = exit_proceeds - pos["entry_outflow"]

                                tax_paid = 0.0
                                if tax_model is not None:
                                    after_tax_pnl, tax_paid = tax_model.apply_to_realized_pnl(realized_pnl)
                                    if tax_paid:
                                        cash -= tax_paid
                                        cumulative_tax += tax_paid
                                else:
                                    after_tax_pnl = realized_pnl

                                cash += exit_proceeds
                                closed += 1

                                realized_rows.append(
                                    {
                                        "ticker": pos["ticker"],
                                        "buy_date": pos["buy_date"],
                                        "sell_date": pos["sell_date"],
                                        "notional": pos["notional"],
                                        "shares": pos["shares"],
                                        "buy_price": pos["buy_price"],
                                        "sell_price": exit_price,
                                        "entry_cost": pos["entry_cost"],
                                        "ftt_cost": float(pos.get("ftt_cost", 0.0)),
                                        "exit_cost": exit_cost,
                                        "realized_pnl": realized_pnl,
                                        "tax_paid": tax_paid,
                                        "after_tax_pnl": after_tax_pnl,
                                        "after_tax_return_pct": (after_tax_pnl / pos["notional"] * 100.0) if pos["notional"] else 0.0,
                                        "exit_is_fallback": bool(pos.get("exit_is_fallback", False)),
                                        "exit_reason": pos.get("exit_reason", ""),
                                    }
                                )
                            else:
                                open_tickers.add(pos["ticker"])
                                open_pos.append(pos)

            # 3) Mark-to-market equity
            if open_pos:
                mtm = 0.0
                for p in open_pos:
                    px_today = px_pivot.at[d, p["ticker"]]
                    if pd.isna(px_today):
                        px_today = p["buy_price"]
                    mtm += float(p["shares"]) * float(px_today)
            else:
                mtm = 0.0

            equity = cash + mtm
            equity_curve.append(
                {
                    "date": d,
                    "equity": float(equity),
                    "cash": float(cash),
                    "open_positions": int(len(open_pos)),
                    "tax_paid": float(cumulative_tax),
                    "executed_trades": int(executed),
                    "closed_trades": int(closed),
                    "dividends_paid": float(dividend_net_paid),
                    "dividends_gross_paid": float(dividend_gross_paid),
                    "dividends_events": int(dividend_payments),
                }
            )

        # Safety net: if anything is still open, force close at the last calendar date.
        if open_pos and len(calendar) > 0:
            last_d = pd.Timestamp(calendar[-1]).normalize()
            for p in list(open_pos):
                px_last = px_pivot.at[last_d, p["ticker"]]
                if pd.isna(px_last):
                    px_last = p["buy_price"]

                exit_gross = float(p["shares"]) * float(px_last)
                exit_cost = cost_model.exit_cost(exit_gross)
                exit_proceeds = exit_gross - exit_cost
                realized_pnl = exit_proceeds - p["entry_outflow"]

                tax_paid = 0.0
                if tax_model is not None:
                    _, tax_paid = tax_model.apply_to_realized_pnl(realized_pnl)
                    if tax_paid:
                        cash -= tax_paid
                        cumulative_tax += tax_paid

                cash += exit_proceeds
                closed += 1
                realized_rows.append(
                    {
                        "ticker": p["ticker"],
                        "buy_date": p["buy_date"],
                        "sell_date": last_d,
                        "notional": p["notional"],
                        "shares": p["shares"],
                        "buy_price": p["buy_price"],
                        "sell_price": float(px_last),
                        "entry_cost": p["entry_cost"],
                        "ftt_cost": float(p.get("ftt_cost", 0.0)),
                        "exit_cost": exit_cost,
                        "realized_pnl": realized_pnl,
                        "tax_paid": tax_paid,
                        "after_tax_pnl": realized_pnl - tax_paid,
                        "after_tax_return_pct": ((realized_pnl - tax_paid) / p["notional"] * 100.0) if p["notional"] else 0.0,
                        "exit_is_fallback": True,
                        "exit_reason": "FORCED_END_OF_BACKTEST",
                    }
                )

            open_pos = []
            open_tickers = set()

            equity_curve[-1]["cash"] = float(cash)
            equity_curve[-1]["equity"] = float(cash)
            equity_curve[-1]["open_positions"] = 0
            equity_curve[-1]["tax_paid"] = float(cumulative_tax)
            equity_curve[-1]["closed_trades"] = int(closed)
            equity_curve[-1]["dividends_paid"] = float(dividend_net_paid)
            equity_curve[-1]["dividends_gross_paid"] = float(dividend_gross_paid)
            equity_curve[-1]["dividends_events"] = int(dividend_payments)

        self.last_realized_trades = pd.DataFrame(realized_rows) if realized_rows else pd.DataFrame()

        if isinstance(getattr(self, "last_audit_stats", None), dict):
            self.last_audit_stats.update(
                {
                    "portfolio_whole_shares": whole_shares,
                    "portfolio_min_trade_notional": min_trade_notional,
                    "portfolio_include_dividends": include_dividends,
                    "portfolio_dividend_withholding_rate": wht,
                    "portfolio_skipped_zero_shares": int(skipped_zero_shares),
                    "portfolio_skipped_min_notional": int(skipped_min_notional),
                    "portfolio_skipped_insufficient_cash": int(skipped_insufficient_cash),
                    "portfolio_skipped_duplicate_ticker": int(skipped_duplicate_ticker),
                    "portfolio_skipped_buy_price_invalid": int(skipped_buy_price_invalid),
                    "portfolio_skipped_capacity": int(skipped_capacity),
                    "portfolio_dividend_entitlements": int(dividend_entitlements),
                    "portfolio_dividend_payments": int(dividend_payments),
                    "portfolio_dividends_gross_paid": float(dividend_gross_paid),
                    "portfolio_dividends_net_paid": float(dividend_net_paid),
                    "portfolio_dividend_rows_skipped_currency": int(dividend_rows_skipped_currency),
                }
            )

        return pd.DataFrame(equity_curve)

