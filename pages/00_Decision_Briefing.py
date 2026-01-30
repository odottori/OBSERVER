from __future__ import annotations

"""Streamlit page: Decision Briefing (trading-facing view).

This page is intentionally "low technical" and designed for daily decisions:
- What to do (top picks)
- Why (headline + sentiment)
- Can I trust it (freshness + last run status)

It preserves full access to the existing technical/operational UI via page links.

Design goals
------------
- Offline-by-default (reads local JSON + optional local DuckDB only)
- Deterministic and resilient to missing artifacts
- Importable under pytest without requiring streamlit (or duckdb) to be installed
"""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None

try:
    import duckdb  # type: ignore
except Exception:  # pragma: no cover
    duckdb = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_DB = ROOT / os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db")


# -----------------------------
# Helpers
# -----------------------------

def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_latest_forecast(reports_dir: Path) -> dict:
    return _read_json(reports_dir / "FORECAST_RANKING_LATEST.json")


def _list_forecast_json_snapshots(reports_dir: Path) -> list[dict]:
    """Return sorted list of snapshots: {asof_date, run_id, path, mtime}."""
    out: list[dict] = []
    if not reports_dir.exists():
        return out

    for p in sorted(reports_dir.glob("FORECAST_RANKING_*.json")):
        if p.name == "FORECAST_RANKING_LATEST.json":
            continue
        obj = _read_json(p)
        meta = (obj.get("meta") or {}) if isinstance(obj, dict) else {}
        asof = meta.get("asof_date")
        rid = meta.get("run_id")
        if not asof:
            continue
        out.append(
            {
                "asof_date": str(asof),
                "run_id": str(rid) if rid else "",
                "path": str(p),
                "mtime": p.stat().st_mtime,
            }
        )

    out.sort(key=lambda x: (x["asof_date"], float(x.get("mtime", 0.0))))
    return out


def _stars_to_badge(x) -> str:
    try:
        n = int(float(x))
        return "★" * max(0, min(5, n))
    except Exception:
        return ""


def _rating_to_action(rating: str) -> str:
    r = (rating or "").strip().upper()
    if r in {"BUY", "OVERWEIGHT", "STRONG BUY"}:
        return "Compra"
    if r in {"DOWNGRADE", "SELL", "UNDERWEIGHT", "STRONG SELL"}:
        return "Evita / Riduci"
    return "Neutro"


def _confidence_bucket(stars, confidence) -> str:
    """Deterministic bucket to avoid overfitting UI semantics."""
    s = 0
    try:
        s = int(float(stars))
    except Exception:
        s = 0

    c = None
    try:
        c = float(confidence)
    except Exception:
        c = None

    if s >= 4:
        return "Alta"
    if s >= 2:
        # If confidence exists, use it as a tie-break.
        if c is not None and c >= 0.6:
            return "Media"
        return "Media"
    return "Bassa"


def _safe_page_link(target: str, label: str) -> None:
    """Use page_link if available; otherwise print a simple label."""
    assert st is not None
    try:
        st.page_link(target, label=label)
    except Exception:
        st.write(f"- {label}: `{target}`")


# -----------------------------
# Optional DuckDB queries
# -----------------------------

def _db_exists(db_path: Path) -> bool:
    try:
        return db_path.exists() and db_path.stat().st_size > 0
    except Exception:
        return False


def _query_one(con, sql: str, params: list | None = None):
    try:
        row = con.execute(sql, params or []).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _load_last_run(con) -> dict:
    """Return last run (dict) or {}."""
    try:
        row = con.execute(
            """
            SELECT run_id, started_at, finished_at, status, universe_id, holding_period_sessions, error
            FROM audit_runs
            ORDER BY COALESCE(finished_at, started_at) DESC
            LIMIT 1
            """
        ).fetchone()
    except Exception:
        row = None

    if not row:
        return {}

    run_id, started_at, finished_at, status, universe_id, hps, error = row
    return {
        "run_id": str(run_id),
        "started_at": str(started_at) if started_at else "",
        "finished_at": str(finished_at) if finished_at else "",
        "status": str(status) if status else "",
        "universe_id": str(universe_id) if universe_id else "",
        "holding_period_sessions": int(hps or 0),
        "error": str(error) if error else "",
    }


def _load_sentiment_timeseries(con, days: int) -> pd.DataFrame:
    """Daily aggregates from recs."""
    days = int(max(1, min(365, days)))
    start = date.today() - timedelta(days=days)
    try:
        df = con.execute(
            """
            SELECT
              date,
              COUNT(*) AS n_recs,
              COUNT(DISTINCT ticker) AS n_tickers,
              AVG(sentiment_score) AS mean_sent
            FROM recs
            WHERE date >= ?
              AND sentiment_score IS NOT NULL
            GROUP BY date
            ORDER BY date
            """,
            [start],
        ).df()
        if df is None or df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def _load_top_tickers_by_sentiment(con, days: int, top_n: int = 10) -> pd.DataFrame:
    days = int(max(1, min(90, days)))
    top_n = int(max(1, min(50, top_n)))
    start = date.today() - timedelta(days=days)
    try:
        df = con.execute(
            """
            SELECT
              ticker,
              AVG(sentiment_score) AS avg_sent,
              COUNT(*) AS n_recs
            FROM recs
            WHERE date >= ?
              AND sentiment_score IS NOT NULL
            GROUP BY ticker
            HAVING COUNT(*) >= 2
            ORDER BY avg_sent DESC
            LIMIT ?
            """,
            [start, top_n],
        ).df()
        if df is None or df.empty:
            return pd.DataFrame()
        df["avg_sent"] = pd.to_numeric(df["avg_sent"], errors="coerce")
        df["n_recs"] = pd.to_numeric(df["n_recs"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def _load_equity_curve(con, run_id: str, days: int = 365) -> pd.DataFrame:
    days = int(max(30, min(3650, days)))
    start = date.today() - timedelta(days=days)
    try:
        df = con.execute(
            """
            SELECT date, equity, cash, invested, positions
            FROM audit_equity
            WHERE run_id = ?
              AND date >= ?
            ORDER BY date
            """,
            [run_id, start],
        ).df()
        if df is None or df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ("equity", "cash", "invested", "positions"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


# -----------------------------
# Render
# -----------------------------

def render() -> None:
    assert st is not None

    st.title("Decision Briefing")
    st.caption(
        "Vista decisionale: azioni consigliate, panorama sentiment, affidabilita (freshness + ultimo run). "
        "Le pagine tecniche restano disponibili per audit e operations."
    )

    with st.sidebar:
        st.header("Sorgenti")
        reports_dir = Path(st.text_input("reports/ directory", value=str(DEFAULT_REPORTS)))
        if not reports_dir.is_absolute():
            reports_dir = (ROOT / reports_dir).resolve()

        db_path = Path(st.text_input("DuckDB path", value=str(DEFAULT_DB)))
        if not db_path.is_absolute():
            db_path = (ROOT / db_path).resolve()

        st.divider()
        browse_history = st.checkbox("Browse timeline (forecast)", value=True)
        top_n = st.number_input("Top N", min_value=1, max_value=200, value=20, step=5)
        sentiment_window_days = st.number_input("Sentiment window (days)", min_value=7, max_value=180, value=30, step=7)

        st.divider()
        st.header("Accesso rapido")
        _safe_page_link("app.py", "Terminal tecnico (home)")
        _safe_page_link("pages/01_Pipeline_Control.py", "Pipeline Control")
        _safe_page_link("pages/02_Gates_Data_Quality.py", "Gates & Data Quality")
        _safe_page_link("pages/03_Audit_Runs.py", "Audit Runs")
        _safe_page_link("pages/04_Trades_Equity.py", "Trades & Equity")
        _safe_page_link("pages/06_Forecasts_Ranking.py", "Forecasts & Ranking (advanced)")
        _safe_page_link("pages/07_NEWS_ALPHA.py", "NEWS-ALPHA (ops)")

    # -----------------------------
    # Data health (DB)
    # -----------------------------
    st.subheader("Stato e affidabilita")

    last_prices = None
    last_recs = None
    last_run = {}

    if duckdb is not None and _db_exists(db_path):
        try:
            con = duckdb.connect(database=str(db_path), read_only=True)
            last_prices = _query_one(con, "SELECT max(date) FROM prices")
            last_recs = _query_one(con, "SELECT max(date) FROM recs")
            last_run = _load_last_run(con)
        except Exception:
            last_run = {}
        finally:
            try:
                con.close()
            except Exception:
                pass

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last prices date", str(last_prices) if last_prices else "(n/a)")
    c2.metric("Last recs date", str(last_recs) if last_recs else "(n/a)")
    c3.metric("Last run status", (last_run.get("status") or "(n/a)"))
    c4.metric("Last run_id", (last_run.get("run_id") or "(n/a)"))

    if last_run and last_run.get("status") and str(last_run.get("status")).upper() != "SUCCESS":
        err = last_run.get("error")
        if err:
            st.error(f"Ultimo run non-success: {err}")

    # -----------------------------
    # Forecast / Top picks
    # -----------------------------
    st.divider()
    st.subheader("Oggi: azioni consigliate (Forecast & Ranking)")

    @st.cache_data(show_spinner=False)
    def _load_latest(_reports_dir: str) -> dict:
        return _read_latest_forecast(Path(_reports_dir))

    @st.cache_data(show_spinner=False)
    def _load_snapshots(_reports_dir: str) -> list[dict]:
        return _list_forecast_json_snapshots(Path(_reports_dir))

    @st.cache_data(show_spinner=False)
    def _load_obj(_path: str) -> dict:
        return _read_json(Path(_path))

    obj: dict = {}
    loaded_from = ""

    if browse_history:
        snaps = _load_snapshots(str(reports_dir))
        if snaps:
            by_date: dict[str, list[dict]] = {}
            for s in snaps:
                by_date.setdefault(s["asof_date"], []).append(s)
            dates_sorted = sorted(by_date.keys())

            if len(dates_sorted) >= 2:
                sel_date = st.select_slider("As-of date", options=dates_sorted, value=dates_sorted[-1])
            else:
                sel_date = dates_sorted[0]
                st.info(f"Only one snapshot date available: {sel_date}")

            choices = by_date.get(sel_date, [])
            if len(choices) > 1:
                labels = [
                    f"{c['asof_date']} | run_id={c['run_id'] or '(none)'} | {Path(c['path']).name}" for c in choices
                ]
                pick = st.selectbox("Snapshot", options=list(range(len(choices))), format_func=lambda i: labels[i])
                chosen = choices[int(pick)]
            else:
                chosen = choices[0]

            obj = _load_obj(chosen["path"])
            loaded_from = chosen["path"]
        else:
            obj = _load_latest(str(reports_dir))
            loaded_from = str(reports_dir / "FORECAST_RANKING_LATEST.json")
    else:
        obj = _load_latest(str(reports_dir))
        loaded_from = str(reports_dir / "FORECAST_RANKING_LATEST.json")

    if not obj:
        st.info(
            "Nessun artifact Forecast/Ranking trovato. Esegui `<PY> scripts/sentinel.py forecast` (Windows: `py`, Linux/macOS: `python`) "
            "o abilita forecasts in certify (SENTINEL_ENABLE_FORECASTS=1)."
        )
    else:
        meta = obj.get("meta") or {}
        diags = obj.get("diagnostics") or {}
        rows = obj.get("rows") or []

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("asof_date", str(meta.get("asof_date") or ""))
        m2.metric("universe", str(meta.get("universe_id") or ""))
        m3.metric("enterable", int(diags.get("enterable_total", 0) or 0))
        m4.metric("candidates", int(diags.get("candidates_total", 0) or 0))

        if loaded_from:
            st.caption(f"Loaded: `{Path(loaded_from).name}`")

        if not rows:
            # Decision-first messaging
            st.warning(
                "Nessuna raccomandazione 'enterable' disponibile per questa data. "
                "Tipicamente significa: right-censoring elevato, prezzi mancanti, o filtri di eseguibilita."
            )
            with st.expander("Dettaglio (diagnostics)", expanded=False):
                st.json({"meta": meta, "diagnostics": diags, "constants": obj.get("constants") or {}})
            st.info("Apri la pagina 'Forecasts & Ranking (advanced)' per ispezionare le cause in dettaglio.")
        else:
            df = pd.DataFrame(rows)

            tick_col = "ticker_effective" if "ticker_effective" in df.columns else ("ticker" if "ticker" in df.columns else None)
            if tick_col is None:
                st.error("Artifact forecast: colonna ticker non trovata.")
            else:
                # Minimal, trading-facing columns
                view = df.copy()
                view["Ticker"] = view[tick_col].astype(str)
                view["Azione"] = view.get("rating", "").astype(str).apply(_rating_to_action)
                view["Stars"] = view.get("stars", "").apply(_stars_to_badge)
                view["Confidenza"] = view.apply(lambda r: _confidence_bucket(r.get("stars"), r.get("confidence")), axis=1)

                # Numeric formatting
                for c in ("forecast_return_pct", "sentiment_score"):
                    if c in view.columns:
                        view[c] = pd.to_numeric(view[c], errors="coerce")

                # Order
                if "rank" in view.columns:
                    view = view.sort_values(["rank"], ascending=[True], kind="mergesort")

                cols = [
                    "rank",
                    "Ticker",
                    "Azione",
                    "Stars",
                    "Confidenza",
                    "forecast_return_pct",
                    "sentiment_score",
                    "headline",
                ]
                cols = [c for c in cols if c in view.columns]

                st.dataframe(view[cols].head(int(top_n)), use_container_width=True, hide_index=True)

                with st.expander("Dettaglio tecnico (meta/diagnostics)", expanded=False):
                    st.json({"meta": meta, "diagnostics": diags, "constants": obj.get("constants") or {}})

    # -----------------------------
    # Sentiment panorama (DB)
    # -----------------------------
    st.divider()
    st.subheader("Panorama: sentiment (da recs)")

    if duckdb is None:
        st.info("DuckDB non disponibile nell'ambiente Python. Installa la dipendenza 'duckdb' per abilitare questa sezione.")
        return

    if not _db_exists(db_path):
        st.info("DB non trovato o vuoto. Verifica il path in sidebar (SENTINEL_ALPHA_DB_PATH).")
        return

    try:
        con = duckdb.connect(database=str(db_path), read_only=True)

        ts = _load_sentiment_timeseries(con, int(sentiment_window_days))
        if ts.empty:
            st.info("Nessun dato di sentiment disponibile in recs per il periodo selezionato.")
        else:
            left, right = st.columns([2, 1])
            with left:
                st.line_chart(ts.set_index("date")["mean_sent"], height=220)
            with right:
                latest = ts.dropna(subset=["mean_sent"]).tail(1)
                if not latest.empty:
                    st.metric("Mean sentiment (last day)", f"{float(latest['mean_sent'].iloc[0]):.3f}")
                st.metric("Days", int(ts["date"].nunique()))
                st.metric("Total recs", int(ts["n_recs"].sum()))

            st.caption("mean_sent = media giornaliera del sentiment_score su recs (tutti i firm).")

            # Volume chart (optional)
            vol = ts.copy()
            vol = vol.set_index("date")["n_recs"]
            st.bar_chart(vol, height=180)

        st.subheader("Top tickers per sentiment (ultimi 14 giorni)")
        top_t = _load_top_tickers_by_sentiment(con, days=14, top_n=10)
        if top_t.empty:
            st.info("Non ci sono abbastanza recs per costruire una classifica per ticker nel periodo.")
        else:
            st.dataframe(top_t, use_container_width=True, hide_index=True)

        # -----------------------------
        # Performance snapshot (latest run)
        # -----------------------------
        st.divider()
        st.subheader("Performance e rischio (ultimo run)")

        if not last_run or not last_run.get("run_id"):
            st.info("Nessun audit_run disponibile. Esegui RUN o CERTIFY dalla pagina Pipeline Control.")
        else:
            rid = last_run["run_id"]
            eq = _load_equity_curve(con, rid, days=365)
            if eq.empty:
                st.info("Nessun dato audit_equity per l'ultimo run.")
            else:
                st.line_chart(eq.set_index("date")["equity"], height=240)

                # Quick drawdown
                e = eq["equity"].astype(float)
                peak = e.cummax()
                dd = (e / peak) - 1.0
                st.metric("Max drawdown (approx)", f"{dd.min():.2%}")

    finally:
        try:
            con.close()
        except Exception:
            pass


if st is not None:  # pragma: no cover
    render()
