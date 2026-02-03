"""Compatibility wrapper around the new audit/backtest core.

Historically this repository exposed `IntelligenceEngine`.
We keep that public surface but delegate to the more rigorous core modules:
- conservative time alignment (no nearest-price joins)
- universe filtering via dynamic historical membership
- explicit cost and tax modeling

This keeps the Streamlit dashboard (`app.py`) and `main.py` stable.
"""

from __future__ import annotations

import os
import json
import time
from pathlib import Path
from dataclasses import replace
from uuid import uuid4

import pandas as pd

from src.phase0.core.audit_engine import AuditEngine, BacktestConfig
from src.phase0.db.audit_store import (
    start_audit_run,
    finish_audit_run,
    persist_trades,
    persist_equity,
    backfill_summary,
)


class IntelligenceEngine:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.path.join("data", "sentinel_alpha.db")
        self._engine = AuditEngine(db_path=self.db_path)

    def close(self) -> None:
        self._engine.close()

    def certify_run(
        self,
        universe_id: str = "ALL",
        holding_period_sessions: int = 22,
        notes: str | None = None,
        save_report_path: str | None = None,
    ) -> tuple[str, str, pd.DataFrame, pd.DataFrame]:
        """Run an audit + portfolio simulation and persist artifacts to DuckDB.

        Returns: (run_id, report_path, trades_df, equity_df)

        This is the *recommended* entrypoint for serious usage because it:
        - assigns a stable run_id
        - persists trades/equity into DuckDB tables
        - allows report/queries without ad-hoc shell commands
        """

        run_id = (os.environ.get("SENTINEL_RUN_ID") or "").strip() or uuid4().hex
        os.environ["SENTINEL_RUN_ID"] = run_id

        # Phase-by-phase timeline (captured in the audit report).
        phase_log: list[dict] = []

        def _phase_start(name: str) -> dict:
            ph = {"phase": name, "status": "RUNNING", "t0": time.perf_counter()}
            phase_log.append(ph)
            return ph

        def _phase_end(ph: dict, status: str = "PASS", **metrics) -> None:
            try:
                dt_ms = int((time.perf_counter() - float(ph.get("t0", 0.0))) * 1000)
            except Exception:
                dt_ms = 0
            ph.pop("t0", None)
            ph["status"] = status
            ph["duration_ms"] = dt_ms
            if metrics:
                ph["metrics"] = metrics

        # Build a resolved, self-contained configuration snapshot.
        # This avoids "(missing)" disclosures in the report and makes the run reproducible
        # even when optional env vars are not explicitly set.
        def _env_bool(name: str, default: bool) -> bool:
            v = os.environ.get(name)
            if v is None or str(v).strip() == "":
                return default
            return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

        def _env_int(name: str, default: int) -> int:
            v = os.environ.get(name)
            if v is None or str(v).strip() == "":
                return int(default)
            try:
                return int(float(str(v).strip()))
            except Exception:
                return int(default)

        def _env_float(name: str, default: float) -> float:
            v = os.environ.get(name)
            if v is None or str(v).strip() == "":
                return float(default)
            try:
                return float(str(v).strip())
            except Exception:
                return float(default)

        def _env_str(name: str, default: str) -> str:
            v = os.environ.get(name)
            if v is None or str(v).strip() == "":
                return str(default)
            return str(v).strip()

        # Raw env snapshot (provenance)
        cfg_env = {
            "SENTINEL_ALLOW_ONLINE_BACKFILL": os.environ.get("SENTINEL_ALLOW_ONLINE_BACKFILL"),
            "SENTINEL_BACKFILL_WINDOW_DAYS": os.environ.get("SENTINEL_BACKFILL_WINDOW_DAYS"),
            "SENTINEL_PRICE_PROVIDER_ORDER": os.environ.get("SENTINEL_PRICE_PROVIDER_ORDER"),
            "SENTINEL_DISABLE_YFINANCE": os.environ.get("SENTINEL_DISABLE_YFINANCE"),
            "SENTINEL_DIVIDEND_POLICY": os.environ.get("SENTINEL_DIVIDEND_POLICY"),
            "SENTINEL_TIMING_MODE": os.environ.get("SENTINEL_TIMING_MODE"),
            "SENTINEL_WHOLE_SHARES": os.environ.get("SENTINEL_WHOLE_SHARES"),
            "SENTINEL_MIN_TRADE_NOTIONAL": os.environ.get("SENTINEL_MIN_TRADE_NOTIONAL"),
            "SENTINEL_INCLUDE_DIVIDENDS": os.environ.get("SENTINEL_INCLUDE_DIVIDENDS"),
            "SENTINEL_DIVIDEND_WITHHOLDING_RATE": os.environ.get("SENTINEL_DIVIDEND_WITHHOLDING_RATE"),
        }

        allow_online_backfill = 1 if _env_bool("SENTINEL_ALLOW_ONLINE_BACKFILL", False) else 0
        backfill_window_days = max(7, min(_env_int("SENTINEL_BACKFILL_WINDOW_DAYS", 90), 365))
        price_provider_order = _env_str("SENTINEL_PRICE_PROVIDER_ORDER", "stooq")
        disable_yfinance = 1 if _env_bool("SENTINEL_DISABLE_YFINANCE", True) else 0
        timing_mode = _env_str("SENTINEL_TIMING_MODE", "T_PLUS_1").upper() or "T_PLUS_1"
        whole_shares = 1 if _env_bool("SENTINEL_WHOLE_SHARES", True) else 0
        min_trade_notional = float(max(0.0, _env_float("SENTINEL_MIN_TRADE_NOTIONAL", 250.0)))
        include_dividends = 1 if _env_bool("SENTINEL_INCLUDE_DIVIDENDS", False) else 0
        wht = float(_env_float("SENTINEL_DIVIDEND_WITHHOLDING_RATE", 0.0))
        if wht < 0.0:
            wht = 0.0
        if wht > 1.0:
            wht = 1.0

        # Effective dividend policy (capability vs run setting)
        div_policy_env = (os.environ.get("SENTINEL_DIVIDEND_POLICY") or "").strip().upper()
        dividend_policy = div_policy_env if div_policy_env else ("B" if include_dividends else "C")

        cfg_resolved = {
            "SENTINEL_ALLOW_ONLINE_BACKFILL": allow_online_backfill,
            "SENTINEL_BACKFILL_WINDOW_DAYS": backfill_window_days,
            "SENTINEL_PRICE_PROVIDER_ORDER": price_provider_order,
            "SENTINEL_DISABLE_YFINANCE": disable_yfinance,
            "SENTINEL_DIVIDEND_POLICY": dividend_policy,
            "SENTINEL_TIMING_MODE": timing_mode,
            "SENTINEL_WHOLE_SHARES": whole_shares,
            "SENTINEL_MIN_TRADE_NOTIONAL": min_trade_notional,
            "SENTINEL_INCLUDE_DIVIDENDS": include_dividends,
            "SENTINEL_DIVIDEND_WITHHOLDING_RATE": wht,
            "env": cfg_env,
        }
        # Attach operational artifacts early so the run is self-contained.
        transcript_path = (os.environ.get("SENTINEL_TRANSCRIPT_PATH") or "").strip() or None
        cfg_resolved["SENTINEL_TRANSCRIPT_PATH"] = transcript_path
        cfg_resolved["artifacts"] = {
            "db_path": self.db_path,
            "transcript_path": transcript_path,
        }

        # Persist run header (idempotent).
        ph = _phase_start("RUN_HEADER_PERSIST")
        start_audit_run(
            self._engine.con,
            run_id=run_id,
            universe_id=universe_id,
            holding_period_sessions=int(holding_period_sessions),
            cfg_obj=cfg_resolved,
            notes=notes,
        )
        _phase_end(ph, status="PASS")

        try:
            ph = _phase_start("TRADE_AUDIT")
            trades = self.run_deep_audit(
                universe_id=universe_id,
                holding_period_sessions=int(holding_period_sessions),
            )
            stats_after_audit = getattr(self._engine, "last_audit_stats", {}) or {}
            _phase_end(
                ph,
                status="PASS",
                trades_rows=int(len(trades)) if trades is not None else 0,
                forced_exits=int(
                    stats_after_audit.get("forced_exits_total", stats_after_audit.get("forced_exits", 0)) or 0
                ),
                backfill_enabled=bool(stats_after_audit.get("backfill_enabled", False)),
                backfill_rows_upserted=int(stats_after_audit.get("backfill_rows_upserted", 0) or 0),
            )

            ph = _phase_start("PORTFOLIO_SIMULATION")
            equity = self.apply_money_management(
                trades,
                universe_id=universe_id,
                holding_period_sessions=int(holding_period_sessions),
            )
            stats_after_port = getattr(self._engine, "last_audit_stats", {}) or {}
            _phase_end(
                ph,
                status="PASS",
                equity_rows=int(len(equity)) if equity is not None else 0,
                executed_trades=int(stats_after_port.get("portfolio_executed_trades", 0) or 0),
                closed_trades=int(stats_after_port.get("portfolio_closed_trades", 0) or 0),
            )

            ph = _phase_start("PERSIST_TRADES")
            persist_trades(self._engine.con, run_id, trades)
            _phase_end(ph, status="PASS", rows=int(len(trades)) if trades is not None else 0)

            ph = _phase_start("PERSIST_EQUITY")
            persist_equity(self._engine.con, run_id, equity)
            _phase_end(ph, status="PASS", rows=int(len(equity)) if equity is not None else 0)

            # Attach phase log for report disclosure (best-effort).
            try:
                if hasattr(self._engine, "last_audit_stats") and isinstance(self._engine.last_audit_stats, dict):
                    self._engine.last_audit_stats["phase_log"] = phase_log
            except Exception:
                pass

            ph = _phase_start("REPORT_WRITE")
            report_path = self.save_master_report(
                trades,
                equity,
                path=save_report_path,
                run_id=run_id,
                phase_log=phase_log,
                transcript_path=transcript_path,
            )
            _phase_end(ph, status="PASS", report_path=str(report_path or ""))

            ph = _phase_start("FINISH_RUN")
            finish_audit_run(self._engine.con, run_id, status="SUCCESS")
            _phase_end(ph, status="PASS")
            return run_id, report_path, trades, equity

        except Exception as e:
            try:
                ph = _phase_start("FINISH_RUN")
                finish_audit_run(self._engine.con, run_id, status="FAILED", error=str(e))
                _phase_end(ph, status="FAIL", error=str(e))
            except Exception:
                finish_audit_run(self._engine.con, run_id, status="FAILED", error=str(e))
            raise



    def run_deep_audit(self, universe_id: str = "ALL", holding_period_sessions: int = 22) -> pd.DataFrame:
        """Return a per-trade audit ledger (gross + net returns)."""

        # Optional multi-provider price backfill can be enabled via env var.
        # This keeps tests and offline certification deterministic by default.
        allow_backfill = os.environ.get("SENTINEL_ALLOW_ONLINE_BACKFILL", "0").strip() in {"1", "true", "TRUE", "yes", "YES"}
        try:
            backfill_days = int(os.environ.get("SENTINEL_BACKFILL_WINDOW_DAYS", "90"))
        except Exception:
            backfill_days = 90
        backfill_days = max(7, min(backfill_days, 365))

        cfg = BacktestConfig(
            holding_period_sessions=holding_period_sessions,
            allow_online_backfill=allow_backfill,
            backfill_window_days=backfill_days,
        )

        trades = self._engine.run_trade_audit(universe_id=universe_id, cfg=cfg)

        # Second pass if we had forced exits: attempt to extend prices and recompute exits.
        stats0 = getattr(self._engine, "last_audit_stats", {}) or {}
        forced = int((stats0.get("forced_exits_total", stats0.get("forced_exits", 0)) ) or 0)
        if allow_backfill and forced > 0:
            bf_stats = self._engine.backfill_prices_for_forced_exits(trades, cfg)
            # Re-run audit to compute the intended holding-period exits if new prices were added.
            trades = self._engine.run_trade_audit(universe_id=universe_id, cfg=cfg)
            # Attach for reporting
            if hasattr(self._engine, "last_audit_stats") and isinstance(self._engine.last_audit_stats, dict):
                self._engine.last_audit_stats.update({
                    "backfill_enabled": True,
                    "backfill_attempts": bf_stats.get("backfill_attempts", 0),
                    "backfill_success": bf_stats.get("backfill_success", 0),
                    "backfill_rows_upserted": bf_stats.get("backfill_rows_upserted", 0),
                })

        return trades

    # --- Portfolio simulation ---
    def apply_money_management(
        self,
        trades_df: pd.DataFrame,
        starting_capital: float = 100000.0,
        universe_id: str | None = None,
        holding_period_sessions: int = 22,
        include_costs: bool = True,
        round_trip_cost_pct: float = 0.0075,
        include_taxes: bool = True,
        capital_gains_rate: float = 0.26,
        max_positions: int = 10,
        cash_reserve_pct: float = 0.20,
        risk_per_trade: float = 0.01,
        max_position_pct: float = 0.20,
        whole_shares: bool | None = None,
        min_trade_notional: float | None = None,
        include_dividends: bool | None = None,
        dividend_withholding_rate: float | None = None,
    ) -> pd.DataFrame:
        """Simulate an overlapping-position portfolio and return an equity curve."""

        def _env_bool(name: str, default: bool) -> bool:
            v = os.environ.get(name)
            if v is None or str(v).strip() == "":
                return default
            return str(v).strip().lower() in {"1","true","yes","y","on"}

        def _env_float(name: str, default: float) -> float:
            v = os.environ.get(name)
            if v is None or str(v).strip() == "":
                return default
            try:
                return float(str(v).strip())
            except Exception:
                return default

        # Retail realism defaults (overrideable via explicit args or env vars)
        ws = whole_shares if whole_shares is not None else _env_bool("SENTINEL_WHOLE_SHARES", True)
        mtn = min_trade_notional if min_trade_notional is not None else _env_float("SENTINEL_MIN_TRADE_NOTIONAL", 250.0)
        inc_div = include_dividends if include_dividends is not None else _env_bool("SENTINEL_INCLUDE_DIVIDENDS", False)
        wht = dividend_withholding_rate if dividend_withholding_rate is not None else _env_float("SENTINEL_DIVIDEND_WITHHOLDING_RATE", 0.0)
        if wht < 0.0:
            wht = 0.0
        if wht > 1.0:
            wht = 1.0

        cfg = BacktestConfig(
            starting_capital=starting_capital,
            holding_period_sessions=holding_period_sessions,
            include_costs=include_costs,
            round_trip_cost_pct=round_trip_cost_pct,
            include_taxes=include_taxes,
            capital_gains_rate=capital_gains_rate,
            max_positions=max_positions,
            cash_reserve_pct=cash_reserve_pct,
            risk_per_trade=risk_per_trade,
            max_position_pct=max_position_pct,
            whole_shares=bool(ws),
            min_trade_notional=float(mtn),
            include_dividends=bool(inc_div),
            dividend_withholding_rate=float(wht),
        )

        # If the caller passed an empty trades_df, compute it.
        if trades_df is None or trades_df.empty:
            uid = universe_id or "ALL"
            trades_df = self._engine.run_trade_audit(uid, cfg=cfg)

        return self._engine.simulate_portfolio(trades_df, cfg=cfg)

    # Backwards-compatible name used by main.py
    def apply_italian_fiscal_model(self, df: pd.DataFrame) -> pd.DataFrame:
        """Legacy alias: portfolio simulation with Italian CGT enabled."""

        return self.apply_money_management(df, include_taxes=True)

    # --- Analytics slices for UI ---
    def get_performance_slices(self, trades_df: pd.DataFrame):
        """Return (by_firm, by_sector, sector_summary) for dashboard rendering."""

        if trades_df is None or trades_df.empty:
            empty = pd.DataFrame()
            return empty, empty, empty

        df = trades_df.copy()
        df["win"] = (df["net_return_pct"] > 0).astype(int)

        by_firm = (
            df.groupby("firm")
            .agg(
                operazioni=("ticker", "count"),
                win_rate=("win", "mean"),
                avg_net_return_pct=("net_return_pct", "mean"),
                avg_risk_vol=("risk_vol", "mean"),
            )
            .reset_index()
        )

        # Simple z-score-like diagnostic (mean / std) on net returns per firm.
        firm_std = df.groupby("firm")["net_return_pct"].std().replace(0, pd.NA)
        firm_mean = df.groupby("firm")["net_return_pct"].mean()
        z = (firm_mean / firm_std).fillna(0.0)
        by_firm["z_score"] = by_firm["firm"].map(z)
        by_firm = by_firm.sort_values(["z_score", "avg_net_return_pct"], ascending=False)

        by_sector = (
            df.groupby("sector")
            .agg(
                operazioni=("ticker", "count"),
                win_rate=("win", "mean"),
                resa_avg=("net_return_pct", "mean"),
            )
            .reset_index()
            .sort_values("resa_avg", ascending=False)
        )

        return by_firm, by_sector, by_sector

    def save_master_report(
        self,
        trades_df: pd.DataFrame,
        equity_df: pd.DataFrame,
        path: str | None = None,
        run_id: str | None = None,
        phase_log: list[dict] | None = None,
        transcript_path: str | None = None,
    ) -> str:
        """Write a deterministic markdown report.

        The report is designed for audit / certification:
        - explicit trade eligibility (universe membership)
        - conservative time alignment
        - modeled friction (slippage/fees) and Italian CGT
        - portfolio equity curve (mark-to-market)
        """

        path = path or os.path.join("reports", "AUDIT_COMPLETE.md")

        rid = (run_id or os.environ.get("SENTINEL_RUN_ID") or "").strip() or None

        # Write both a stable "latest" report and a run-scoped immutable copy.
        # This keeps legacy behavior (reports/AUDIT_COMPLETE.md) while allowing
        # operators to browse historical runs in Streamlit without losing artifacts.
        primary_path = Path(path)
        paths_to_write: list[Path] = [primary_path]
        archive_path: Path | None = None
        if rid and primary_path.name == "AUDIT_COMPLETE.md":
            archive_path = primary_path.with_name(f"AUDIT_COMPLETE_{rid}.md")
            if archive_path != primary_path:
                paths_to_write.append(archive_path)

        for p in paths_to_write:
            os.makedirs(str(p.parent), exist_ok=True)

        def _df_to_md(df: pd.DataFrame, max_rows: int = 200) -> str:
            if df is None:
                return ""
            df = df.head(max_rows).copy()
            try:
                return df.to_markdown(index=False)
            except Exception:
                # Fallback: plain markdown pipe table (no external dependencies)
                cols = list(df.columns)
                lines = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
                for row in df.itertuples(index=False):
                    lines.append("|" + "|".join(str(x) for x in row) + "|")
                return "\n".join(lines)

        result_path = str(primary_path)

        files = [open(str(p), "w", encoding="utf-8") for p in paths_to_write]
        try:
            def w(txt: str) -> None:
                for _f in files:
                    _f.write(txt)

            w("# SENTINEL-ALPHA: Institutional Audit (DuckDB)\n\n")
            w("This report is generated from the DuckDB audit pipeline.\n\n")

            if rid:
                w("## Certification Run\n\n")
                w(f"- run_id: `{rid}`\n")
                # Best-effort include code fingerprint if available
                try:
                    fp = self._engine.con.execute(
                        "SELECT code_fingerprint FROM audit_runs WHERE run_id = ?",
                        [rid],
                    ).fetchone()
                    if fp and fp[0]:
                        w(f"- code_fingerprint: `{fp[0]}`\n")
                except Exception:
                    pass
                w("\n")

                # Best-effort include run configuration snapshot if available.
                cfg_raw = None
                try:
                    cfg_row = self._engine.con.execute(
                        "SELECT config_json FROM audit_runs WHERE run_id = ?",
                        [rid],
                    ).fetchone()
                    if cfg_row and cfg_row[0]:
                        cfg_raw = cfg_row[0]
                except Exception:
                    cfg_raw = None

                if cfg_raw:
                    w("## Run Configuration (from audit_runs.config_json)\n\n")

                    cfg: dict = {}
                    cfg_env: dict = {}
                    parse_ok = False
                    try:
                        parsed = json.loads(cfg_raw)
                        if isinstance(parsed, dict):
                            cfg = parsed
                            parse_ok = True
                            if isinstance(cfg.get("env"), dict):
                                cfg_env = cfg.get("env") or {}
                    except Exception:
                        cfg = {}
                        cfg_env = {}
                        parse_ok = False

                    if not parse_ok:
                        w("> Note: config_json was present but could not be parsed as JSON (best-effort disclosure).\n\n")

                    keys = [
                        "SENTINEL_ALLOW_ONLINE_BACKFILL",
                        "SENTINEL_BACKFILL_WINDOW_DAYS",
                        "SENTINEL_PRICE_PROVIDER_ORDER",
                        "SENTINEL_DISABLE_YFINANCE",
                        "SENTINEL_DIVIDEND_POLICY",
                        "SENTINEL_TIMING_MODE",
                        "SENTINEL_WHOLE_SHARES",
                        "SENTINEL_MIN_TRADE_NOTIONAL",
                        "SENTINEL_INCLUDE_DIVIDENDS",
                        "SENTINEL_DIVIDEND_WITHHOLDING_RATE",
                    ]

                    def _cfg_lookup(k: str):
                        if isinstance(cfg, dict) and k in cfg:
                            return cfg.get(k)
                        if isinstance(cfg_env, dict) and k in cfg_env:
                            return cfg_env.get(k)

                        # Resolve defaults so the report is self-contained.
                        # These defaults mirror the runtime defaults used by the pipeline.
                        defaults = {
                            "SENTINEL_ALLOW_ONLINE_BACKFILL": 0,
                            "SENTINEL_BACKFILL_WINDOW_DAYS": 90,
                            "SENTINEL_PRICE_PROVIDER_ORDER": "stooq",
                            "SENTINEL_DISABLE_YFINANCE": 1,
                            "SENTINEL_TIMING_MODE": "T_PLUS_1",
                            "SENTINEL_WHOLE_SHARES": 1,
                            "SENTINEL_MIN_TRADE_NOTIONAL": 250.0,
                            "SENTINEL_INCLUDE_DIVIDENDS": 0,
                            "SENTINEL_DIVIDEND_WITHHOLDING_RATE": 0.0,
                        }

                        if k == "SENTINEL_DIVIDEND_POLICY":
                            # If not explicitly present, derive from include_dividends.
                            inc_raw = _cfg_lookup("SENTINEL_INCLUDE_DIVIDENDS")
                            try:
                                inc = int(bool(inc_raw)) if isinstance(inc_raw, bool) else int(float(str(inc_raw)))
                            except Exception:
                                inc = int(defaults.get("SENTINEL_INCLUDE_DIVIDENDS", 0))
                            return "B" if inc else "C"

                        return defaults.get(k)

                    def _value_to_str(v) -> str:
                        if v is None:
                            return "(missing)"
                        if isinstance(v, bool):
                            return "true" if v else "false"
                        if isinstance(v, (int, float)):
                            return str(v)
                        if isinstance(v, (dict, list)):
                            try:
                                return json.dumps(v, sort_keys=True)
                            except Exception:
                                return str(v)
                        return str(v)

                    for k in keys:
                        w(f"- {k}: `{_value_to_str(_cfg_lookup(k))}`\n")
                    w("\n")



            # --- Artifacts & Operational Logs ---
            w("## Artifacts & Operational Logs\n\n")
            w(f"- Report path (latest): `{str(primary_path)}`\n")
            if archive_path is not None:
                w(f"- Report archive: `{str(archive_path)}`\n")
            w(f"- DB path: `{self.db_path}`\n")
            tp = transcript_path or (os.environ.get('SENTINEL_TRANSCRIPT_PATH') or '').strip()
            if tp:
                w(f"- Transcript: `{tp}`\n")
            w("\n")

            # --- Wave 6: Pre-trade Forecasts & Ranking ---
            w("## Pre-trade Forecasts & Ranking\n\n")
            enabled = os.environ.get("SENTINEL_ENABLE_FORECASTS")
            w(
                "This section links the deterministic, offline-by-default pre-trade ranking artifacts "
                "(Wave 6). Forecast calibration is leak-safe: it uses only audit_trades.signal_date < asof_date.\n\n"
            )
            w(f"- SENTINEL_ENABLE_FORECASTS: `{enabled if (enabled is not None and str(enabled).strip() != '') else '(default=1)'}`\n")

            rep_dir = primary_path.parent
            fr_json = None
            fr_md = None
            fr_latest = rep_dir / "FORECAST_RANKING_LATEST.json"
            if rid:
                fr_json = rep_dir / f"FORECAST_RANKING_{rid}.json"
                fr_md = rep_dir / f"FORECAST_RANKING_{rid}.md"

            if fr_json is not None and fr_json.exists():
                w("- Artifacts:\n")
                w(f"  - JSON: `{str(fr_json)}`\n")
                if fr_md is not None:
                    w(f"  - Markdown: `{str(fr_md)}`\n")
                if fr_latest.exists():
                    w(f"  - Latest JSON: `{str(fr_latest)}`\n")
                w("\n")

                # Best-effort include a compact Top-N table in the master report.
                try:
                    raw = fr_json.read_text(encoding="utf-8")
                    obj = json.loads(raw)
                    rows = obj.get("rows") or []
                    df = pd.DataFrame(rows)
                    if not df.empty:
                        cols = [
                            "rank",
                            "stars",
                            "ticker_effective",
                            "firm",
                            "rating",
                            "forecast_return_pct",
                            "confidence",
                            "headline",
                        ]
                        df2 = df[[c for c in cols if c in df.columns]].copy()
                        if "stars" in df2.columns:
                            df2["stars"] = df2["stars"].map(lambda x: "★" * int(x) if x is not None else "")
                        if "forecast_return_pct" in df2.columns:
                            df2["forecast_return_pct"] = df2["forecast_return_pct"].map(lambda x: f"{float(x):.2f}" if x is not None else "")
                        if "confidence" in df2.columns:
                            df2["confidence"] = df2["confidence"].map(lambda x: f"{float(x):.2f}" if x is not None else "")
                        df2 = df2.head(25)
                        w("### Top 25 (from FORECAST_RANKING)\n\n")
                        w(_df_to_md(df2, max_rows=25))
                        w("\n\n")
                    else:
                        w("> Note: forecast artifact exists but contains zero enterable rows for this as-of date.\n\n")
                except Exception:
                    w("> Note: unable to parse forecast JSON (best-effort). Refer to the linked artifacts.\n\n")
            else:
                w(
                    "> Note: forecast artifacts were not found for this run. "
                    "This can happen if forecasts were disabled (SENTINEL_ENABLE_FORECASTS=0) "
                    "or if the forecast step failed before report generation.\n\n"
                )

            # --- Audit Timeline (phase-by-phase) ---
            pl = phase_log
            if pl is None:
                try:
                    st = getattr(self._engine, 'last_audit_stats', {}) or {}
                    if isinstance(st, dict) and isinstance(st.get('phase_log'), list):
                        pl = st.get('phase_log')
                except Exception:
                    pl = None

            if pl:
                w("## Audit Timeline (phase-by-phase)\n\n")
                total = len(pl)
                passed = sum(1 for x in pl if str(x.get('status','')).upper() == 'PASS')
                w(f"Completed phases: {passed}/{total} PASS\n\n")

                w("|#|Phase|Status|Duration (ms)|Key metrics|\n|---:|---|---|---:|---|\n")
                for i, ph in enumerate(pl, start=1):
                    name = str(ph.get('phase',''))
                    status = str(ph.get('status',''))
                    dur = int(ph.get('duration_ms', 0) or 0)
                    metrics = ph.get('metrics') or {}
                    if isinstance(metrics, dict) and metrics:
                        kv = []
                        for k, v in metrics.items():
                            if v is None:
                                continue
                            s = str(v)
                            if len(s) > 40:
                                s = s[:37] + '...'
                            kv.append(f"{k}={s}")
                        km = ', '.join(kv[:6])
                    else:
                        km = ''
                    w(f"|{i}|{name}|{status}|{dur}|{km}|\n")
                w("\n")

                # Extra detail: dump per-phase metrics in a stable, readable format.
                w("### Phase Details\n\n")
                for ph in pl:
                    name = str(ph.get("phase", ""))
                    status = str(ph.get("status", ""))
                    dur = int(ph.get("duration_ms", 0) or 0)
                    w(f"- **{name}** — {status} ({dur} ms)\n")
                    metrics = ph.get("metrics") or {}
                    if isinstance(metrics, dict) and metrics:
                        for k, v in metrics.items():
                            if v is None:
                                continue
                            w(f"  - {k}: `{v}`\n")
                    w("\n")

            # --- Run stats ---
            stats = getattr(self._engine, "last_audit_stats", {}) or {}
            if stats:
                w("## Run Parameters & Eligibility\n\n")
                w(f"- Universe: `{stats.get('universe_id','ALL')}`\n")

                # Include pre-audit input gate counters (coverage + right-censoring) so the
                # report and the operator preflight output are numerically comparable.
                try:
                    cov = self._engine.verify_signal_price_coverage(
                        universe_id=str(stats.get("universe_id", "ALL") or "ALL"),
                        sample_limit=0,
                    )
                    elig_total = int(cov.get("eligible_signals", 0) or 0)
                    rc = int(cov.get("signals_right_censored", 0) or 0)
                    miss = int(cov.get("signals_missing_price_series", 0) or 0)
                    norm = int(cov.get("signals_normalization_changed", 0) or 0)
                    mapped = int(cov.get("signals_mapping_applied", 0) or 0)
                    elig_enterable = max(0, elig_total - rc)
                    w(
                        "- Input gate (signal coverage): "
                        f"eligible_enterable={elig_enterable}; eligible_total={elig_total}; "
                        f"right_censored={rc}; missing_price_series={miss}; "
                        f"normalized_signals={norm}; mapped_signals={mapped}\n"
                    )
                except Exception:
                    pass

                # Include ticker mapping gate counters so the report is self-contained.
                # The runner enforces this gate before the audit starts; here we only
                # disclose the observed table integrity state.
                try:
                    from src.phase0.tools.verify_ticker_mappings import check_ticker_mappings

                    mrep = check_ticker_mappings(self._engine.con, sample_limit=0, enable_warnings=False)
                    w(
                        "- Mapping gate (ticker_mappings): "
                        f"rows={int(mrep.get('n_rows', 0) or 0)}; "
                        f"aliases={int(mrep.get('n_aliases', 0) or 0)}; "
                        f"overlaps={int(mrep.get('n_overlaps', 0) or 0)}; "
                        f"cycles={int(mrep.get('n_cycles', 0) or 0)}; "
                        f"invalid={int(mrep.get('n_invalid', 0) or 0)}\n"
                    )
                except Exception:
                    pass

                # Include provenance gate counters so the report is self-contained.
                # The runner enforces this gate before the audit starts; here we only
                # disclose the observed table provenance state.
                try:
                    placeholder_regex = (
                        r"^https?://(www\.)?(example\.(com|org|net)|localhost)([:/]|$)"
                        r"|^https?://(127\.0\.0\.1|0\.0\.0\.0)([:/]|$)"
                    )
                    total_checked = int(
                        self._engine.con.execute("SELECT COUNT(*) FROM recs").fetchone()[0] or 0
                    )
                    mh, msu, mpa = self._engine.con.execute(
                        """
                        SELECT
                            SUM(CASE WHEN headline IS NULL OR length(trim(headline)) = 0 THEN 1 ELSE 0 END) AS missing_headline,
                            SUM(CASE WHEN source_url IS NULL OR length(trim(source_url)) = 0 THEN 1 ELSE 0 END) AS missing_source_url,
                            SUM(CASE WHEN published_at IS NULL THEN 1 ELSE 0 END) AS missing_published_at
                        FROM recs
                        """
                    ).fetchone()
                    missing_headline = int(mh or 0)
                    missing_source_url = int(msu or 0)
                    missing_published_at = int(mpa or 0)
                    non_http_urls, placeholder_urls = self._engine.con.execute(
                        f"""
                        SELECT
                            SUM(CASE WHEN source_url IS NOT NULL AND length(trim(source_url)) > 0
                                     AND NOT (lower(trim(source_url)) LIKE 'http://%' OR lower(trim(source_url)) LIKE 'https://%')
                                THEN 1 ELSE 0 END) AS non_http_urls,
                            SUM(CASE WHEN source_url IS NOT NULL AND length(trim(source_url)) > 0
                                     AND regexp_matches(lower(trim(source_url)), '{placeholder_regex}')
                                THEN 1 ELSE 0 END) AS placeholder_urls
                        FROM recs
                        """
                    ).fetchone()
                    non_http_urls = int(non_http_urls or 0)
                    placeholder_urls = int(placeholder_urls or 0)

                    unsafe = any(
                        x > 0
                        for x in (
                            missing_headline,
                            missing_source_url,
                            missing_published_at,
                            non_http_urls,
                            placeholder_urls,
                        )
                    )
                    status = "UNSAFE" if unsafe else "SAFE"
                    w(
                        "- Provenance gate (recs): "
                        f"status={status}; total_checked={total_checked}; "
                        f"missing_headline={missing_headline}; missing_source_url={missing_source_url}; "
                        f"missing_published_at={missing_published_at}; non_http_urls={non_http_urls}; "
                        f"placeholder_urls={placeholder_urls}\n"
                    )
                except Exception:
                    pass

                # A7.0: explicit contracts that materially affect retail realism.
                timing_mode = (os.environ.get("SENTINEL_TIMING_MODE") or "T_PLUS_1").strip().upper() or "T_PLUS_1"

                # Dividend policy disclosure: separate "requested" policy (if any) from the
                # *effective* run setting (driven by include_dividends).
                # This avoids confusing states like "Policy B" while dividends modeling is disabled.
                div_policy_env = (os.environ.get("SENTINEL_DIVIDEND_POLICY") or "").strip().upper()
                inc_hint = stats.get("portfolio_include_dividends", None)
                if inc_hint is None:
                    inc_env = (os.environ.get("SENTINEL_INCLUDE_DIVIDENDS") or "0").strip()
                    inc = inc_env not in ("0", "false", "False", "no", "NO", "")
                else:
                    inc = bool(inc_hint)

                # Effective policy is determined by the run setting.
                div_policy_effective = "B" if inc else "C"
                div_policy_requested = div_policy_env or None
                div_policy = div_policy_effective

                w(f"- Timing contract: `{timing_mode}` (signal day D → entry next trading session open)\n")
                if div_policy_requested and div_policy_requested != div_policy_effective:
                    w(
                        f"- Dividend policy (requested): `{div_policy_requested}` (overridden by run setting → `{div_policy_effective}`)\n"
                    )

                if div_policy == "B":
                    w(
                        "- Dividend policy: `B` (unadjusted prices; cash dividends modeled as portfolio cashflows when enabled)\n"
                    )
                elif div_policy == "C":
                    w(
                        "- Dividend policy: `C` (dividends ignored; NOT CERTIFIABLE under DR-1 unless explicitly accepted)\n"
                    )
                else:
                    w(
                        f"- Dividend policy: `{div_policy}` (non-standard; see DR-1 for allowed policies)\n"
                    )

                # Portfolio-level retail knobs (available after portfolio simulation)
                if "portfolio_whole_shares" in stats or "portfolio_min_trade_notional" in stats:
                    try:
                        ws = bool(stats.get("portfolio_whole_shares", False))
                    except Exception:
                        ws = False
                    try:
                        mtn = float(stats.get("portfolio_min_trade_notional", 0.0) or 0.0)
                    except Exception:
                        mtn = 0.0
                    w(f"- Retail execution: whole_shares={ws}, min_trade_notional={mtn:.2f}\n")

                    inc = bool(stats.get("portfolio_include_dividends", False))
                    if inc:
                        try:
                            wht = float(stats.get("portfolio_dividend_withholding_rate", 0.0) or 0.0)
                        except Exception:
                            wht = 0.0
                        w(f"- Dividends modeling: ENABLED (withholding_rate={wht:.2f})\n")
                        w(f"  - Dividend payments: {int(stats.get('portfolio_dividend_payments', 0) or 0)} events\n")
                        w(f"  - Dividends paid: gross={float(stats.get('portfolio_dividends_gross_paid', 0.0) or 0.0):,.2f}, net={float(stats.get('portfolio_dividends_net_paid', 0.0) or 0.0):,.2f}\n")
                    else:
                        w("- Dividends modeling: DISABLED (Policy C / dividends ignored; NOT CERTIFIABLE under DR-1 unless explicitly accepted)\n")

                    w(
                        "- Execution skips: "
                        f"duplicate_ticker={int(stats.get('portfolio_skipped_duplicate_ticker', 0) or 0)}, "
                        f"capacity={int(stats.get('portfolio_skipped_capacity', 0) or 0)}, "
                        f"zero_shares={int(stats.get('portfolio_skipped_zero_shares', 0) or 0)}, "
                        f"min_notional={int(stats.get('portfolio_skipped_min_notional', 0) or 0)}, "
                        f"cash={int(stats.get('portfolio_skipped_insufficient_cash', 0) or 0)}, "
                        f"invalid_buy_price={int(stats.get('portfolio_skipped_buy_price_invalid', 0) or 0)}"
                        "\n"
                    )

                if "eligible_signals" in stats:
                    w(f"- Eligible signals (post membership filter): {int(stats.get('eligible_signals', 0))}\n")
                if "eligible_trades_dedup" in stats:
                    w(f"- Eligible trades (deduplicated): {int(stats.get('eligible_trades_dedup', 0))}\n")
                if "dedup_dropped" in stats:
                    w(f"- Dedup dropped: {int(stats.get('dedup_dropped', 0))}\n")
                forced_total = int(stats.get('forced_exits_total', stats.get('forced_exits', 0)) or 0)
                fallback_exits = int(stats.get('fallback_exits', 0) or 0)
                m2m_exits = int(stats.get('mark_to_market_exits', 0) or 0)
                w(f"- Exit exceptions (total): {forced_total}\n")
                w(f"  - Fallback exits (missing forward prices): {fallback_exits}\n")
                w(f"  - Mark-to-market exits (end-of-data): {m2m_exits}\n")
                if "skipped" in stats or "skipped_signals" in stats:
                    w(f"- Skipped signals (halts/shift limits): {int(stats.get('skipped', stats.get('skipped_signals', 0)))}\n")
                if "entry_shifted" in stats:
                    w(f"- Entry shifted (halts): {int(stats.get('entry_shifted', 0))}\n")
                if "exit_shifted" in stats:
                    w(f"- Exit shifted (halts): {int(stats.get('exit_shifted', 0))}\n")
                if "tobin_trades" in stats:
                    w(f"- Tobin/FTT applicable trades: {int(stats.get('tobin_trades', 0))}\n")
                if "total_ftt_estimate" in stats:
                    w(f"- Tobin/FTT estimate (trade-level): {float(stats.get('total_ftt_estimate', 0.0)):.4f}% notional (aggregate)\n")
                if stats.get("backfill_enabled"):
                    w("- Online backfill: ENABLED (env `SENTINEL_ALLOW_ONLINE_BACKFILL=1`)\n")
                    w(f"  - Backfill attempts: {int(stats.get('backfill_attempts', 0))}\n")
                    w(f"  - Backfill successes: {int(stats.get('backfill_success', 0))}\n")
                    # Prefer DB-logged accounting if available.
                    upserted = int(stats.get('backfill_rows_upserted', 0) or 0)
                    inserted = None
                    updated_est = None
                    try:
                        cols = {r[1] for r in self._engine.con.execute("PRAGMA table_info('data_gaps')").fetchall()}
                        has_upserted = 'rows_upserted' in cols
                        if has_upserted:
                            row = self._engine.con.execute(
                                """
                                SELECT
                                  SUM(COALESCE(rows_inserted,0)) AS ins,
                                  SUM(COALESCE(rows_upserted,0)) AS ups
                                FROM data_gaps
                                WHERE run_id = ?
                                """,
                                [rid],
                            ).fetchone()
                            if row is not None:
                                inserted = int(row[0] or 0)
                                ups_db = int(row[1] or 0)
                                if ups_db > 0:
                                    upserted = ups_db
                                updated_est = max(0, upserted - inserted)
                    except Exception:
                        pass

                    w(f"  - Rows upserted into prices (new+updated): {upserted}\n")
                    if inserted is not None:
                        w(f"  - Rows newly inserted (new rows only): {inserted}\n")
                        w(f"  - Rows updated (estimated): {int(updated_est or 0)}\n")
                # Retail execution knobs (portfolio simulation)
                ws = stats.get("portfolio_whole_shares", None)
                if ws is not None:
                    try:
                        w(f"- Retail execution: whole_shares={bool(ws)}; min_trade_notional={float(stats.get('portfolio_min_trade_notional', 0.0) or 0.0):.2f}\n")
                    except Exception:
                        w(f"- Retail execution: whole_shares={ws}; min_trade_notional={stats.get('portfolio_min_trade_notional', 0.0)}\n")
                    w(f"  - Skipped (zero shares): {int(stats.get('portfolio_skipped_zero_shares', 0) or 0)}\n")
                    w(f"  - Skipped (min notional): {int(stats.get('portfolio_skipped_min_notional', 0) or 0)}\n")
                    w(f"  - Skipped (cash): {int(stats.get('portfolio_skipped_insufficient_cash', 0) or 0)}\n")
                    w(f"  - Skipped (duplicate ticker): {int(stats.get('portfolio_skipped_duplicate_ticker', 0) or 0)}\n")
                    w(f"  - Skipped (capacity): {int(stats.get('portfolio_skipped_capacity', 0) or 0)}\n")
                div_on = bool(stats.get("portfolio_include_dividends", False))
                if div_on:
                    w(f"- Dividends: ENABLED (withholding_rate={float(stats.get('portfolio_dividend_withholding_rate', 0.0) or 0.0):.4f})\n")
                    w(f"  - Gross paid: {float(stats.get('portfolio_dividends_gross_paid', 0.0) or 0.0):,.2f}\n")
                    w(f"  - Net paid: {float(stats.get('portfolio_dividends_net_paid', 0.0) or 0.0):,.2f}\n")
                    w(f"  - Payment events: {int(stats.get('portfolio_dividend_payments', 0) or 0)}\n")
                else:
                    w(
                        "- Dividends: DISABLED (Policy C / dividends ignored; NOT CERTIFIABLE by default; set env SENTINEL_INCLUDE_DIVIDENDS=1 to enable Policy B)\n"
                    )

                w("\n")

            # --- Backfill / data provenance summary ---
            if rid:
                try:
                    bf = backfill_summary(self._engine.con, rid)
                except Exception:
                    bf = pd.DataFrame()
                if bf is not None and not bf.empty:
                    w("## Backfill & Data Integrity\n\n")
                    w("Backfill attempts (provider/status aggregation) for this run:\n\n")
                    w(_df_to_md(bf, max_rows=200))
                    w("\n\n")

            if equity_df is not None and not equity_df.empty:
                start = equity_df["equity"].iloc[0]
                end = equity_df["equity"].iloc[-1]
                roi = ((end / start) - 1.0) * 100.0
                w("## Portfolio Summary\n\n")
                w(f"- Starting capital: {start:,.2f}\n")
                w(f"- Final capital: {end:,.2f}\n")
                w(f"- ROI: {roi:.2f}%\n")
                w(f"- Total tax paid (cumulative): {equity_df['tax_paid'].iloc[-1]:,.2f}\n")

                # Risk metrics from mark-to-market daily equity
                eq = equity_df.copy()
                eq["date"] = pd.to_datetime(eq["date"], errors="coerce")
                eq = eq.dropna(subset=["date"]).sort_values("date")
                eq = eq.set_index("date")
                ret = eq["equity"].pct_change().dropna()
                if not ret.empty:
                    vol = float(ret.std()) * (252.0 ** 0.5)
                    sharpe = (float(ret.mean()) / float(ret.std()) * (252.0 ** 0.5)) if float(ret.std()) != 0 else 0.0
                else:
                    vol, sharpe = 0.0, 0.0

                peak = eq["equity"].cummax()
                dd = (eq["equity"] / peak) - 1.0
                max_dd = float(dd.min()) * 100.0 if not dd.empty else 0.0

                days = max(1, int((eq.index[-1] - eq.index[0]).days))
                years = days / 365.25
                cagr = ((end / start) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0

                w(f"- CAGR (approx): {cagr:.2f}%\n")
                w(f"- Volatility (ann.): {vol*100.0:.2f}%\n")
                w(f"- Sharpe (rf=0): {sharpe:.2f}\n")
                w(f"- Max Drawdown: {max_dd:.2f}%\n")

                if "executed_trades" in equity_df.columns:
                    w(f"- Executed trades: {int(equity_df['executed_trades'].iloc[-1])}\n")
                if "closed_trades" in equity_df.columns:
                    w(f"- Closed trades: {int(equity_df['closed_trades'].iloc[-1])}\n")
                w("\n")

                # Realized trade outcomes (post costs, post tax)
                realized = getattr(self._engine, "last_realized_trades", None)
                if realized is not None and not realized.empty:
                    w("## Realized Trades (executed)\n\n")
                    rcols = [
                        "ticker",
                        "buy_date",
                        "sell_date",
                        "notional",
                        "entry_cost",
                        "ftt_cost",
                        "exit_cost",
                        "realized_pnl",
                        "tax_paid",
                        "after_tax_pnl",
                        "after_tax_return_pct",
                        "exit_reason",
                    ]
                    exist_r = [c for c in rcols if c in realized.columns]
                    w(_df_to_md(realized[exist_r].sort_values("buy_date")))
                    w("\n\n")

            if trades_df is None or trades_df.empty:
                w("## Trades\n\nNo eligible trades were produced.\n")
            else:
                w("## Trades (eligible ledger)\n\n")
                cols = [
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
                    "sentiment_score",
                    "is_tobin_tax",
                    "ftt_pct",
                    "exec_shift_sessions",
                    "exit_shift_sessions",
                    "halt_reason",
                    "gross_return_pct",
                    "cost_pct",
                    "net_return_pct",
                    "trade_score",
                ]
                exist = [c for c in cols if c in trades_df.columns]
                w(_df_to_md(trades_df[exist]))
                w("\n")

                # Raw ledger (pre-dedup): kept for forensic audit
                raw = getattr(self._engine, "last_trade_ledger_raw", None)
                if raw is not None and not raw.empty and len(raw) != len(trades_df):
                    w("\n## Trades (raw eligible, pre-dedup)\n\n")
                    exist_raw = [c for c in cols if c in raw.columns]
                    w(_df_to_md(raw[exist_raw]))
                    w("\n")

        finally:
            for _f in files:
                try:
                    _f.close()
                except Exception:
                    pass

        return result_path
