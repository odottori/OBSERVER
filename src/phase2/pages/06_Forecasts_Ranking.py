from __future__ import annotations

"""Streamlit page: Wave 6 Forecasts, Stars & Ranking.

Enhancements (post-Wave6)
------------------------
- Timeline browsing across available forecast artifacts (days with info)
- Outcome-aware star coloring for historical dates (green/red when outcome known)

Design goals
------------
- Offline-by-default (reads local JSON + optional local DuckDB only)
- Deterministic and resilient to missing artifacts
- Importable under pytest without requiring streamlit (or duckdb) to be installed
"""

import json
import os
from datetime import date
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


def _repo_root() -> Path:
    """Best-effort repo root discovery (works from /pages and /src/*)."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / 'src').is_dir() and (parent / '.doc').is_dir():
            return parent
    # Fallback: historical assumption (file lives under repo/pages/)
    return p.parents[1]

ROOT = _repo_root()
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_DB = ROOT / os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_latest_json(reports_dir: Path) -> dict:
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
            # Fallback: attempt to parse YYYY-MM-DD from filename.
            stem = p.stem
            parts = stem.split("_")
            for part in reversed(parts):
                if len(part) == 10 and part[4] == "-" and part[7] == "-":
                    asof = part
                    break
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

    # Sort by asof_date, then mtime as deterministic tie-break
    out.sort(key=lambda x: (x["asof_date"], float(x.get("mtime", 0.0))))
    return out


def _stars(x) -> str:
    try:
        n = int(x)
        return "★" * max(0, min(5, n))
    except Exception:
        return ""


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def _load_trade_outcomes(
    db_path: Path,
    signal_date: date,
    tickers: list[str],
) -> tuple[pd.DataFrame, date | None]:
    """Return (outcomes_df, max_signal_date).

    outcomes_df columns:
      - ticker
      - trade_executed (bool)
      - net_return_pct (float)
      - buy_date (date/None)
      - sell_date (date/None)

    If duckdb/db missing, returns (empty_df, None).
    """
    if duckdb is None:
        return pd.DataFrame(), None
    if not db_path.exists():
        return pd.DataFrame(), None
    if not tickers:
        return pd.DataFrame(), None

    try:
        con = duckdb.connect(database=str(db_path), read_only=True)
    except Exception:
        return pd.DataFrame(), None

    try:
        # Determine the latest signal_date available in audit_trades (used to classify "pending").
        try:
            max_sig = con.execute("SELECT max(signal_date) FROM audit_trades").fetchone()[0]
            max_sig_date = max_sig if isinstance(max_sig, date) else _parse_date(str(max_sig))
        except Exception:
            max_sig_date = None

        # Query outcomes for the selected day.
        df_t = pd.DataFrame({"ticker": [str(t) for t in tickers]})
        con.register("df_tickers", df_t)
        try:
            q = (
                "SELECT ticker, net_return_pct, buy_date, sell_date "
                "FROM audit_trades "
                "WHERE signal_date = ? "
                "AND ticker IN (SELECT ticker FROM df_tickers)"
            )
            rows = con.execute(q, [signal_date]).fetchdf()
        finally:
            try:
                con.unregister("df_tickers")
            except Exception:
                pass

        if rows is None or len(rows) == 0:
            return pd.DataFrame(), max_sig_date

        out = rows.copy()
        out["ticker"] = out["ticker"].astype(str)
        out["trade_executed"] = True
        # Deduplicate by ticker deterministically: keep last row by (sell_date, buy_date, net_return_pct).
        for col in ("sell_date", "buy_date"):
            if col in out.columns:
                out[col] = pd.to_datetime(out[col], errors="coerce").dt.date
        if "net_return_pct" in out.columns:
            out["net_return_pct"] = pd.to_numeric(out["net_return_pct"], errors="coerce")
        out = out.sort_values(
            ["ticker", "sell_date", "buy_date", "net_return_pct"],
            ascending=[True, True, True, True],
            kind="mergesort",
        ).drop_duplicates(subset=["ticker"], keep="last")

        return out, max_sig_date
    finally:
        try:
            con.close()
        except Exception:
            pass


def render() -> None:
    assert st is not None

    st.title("Forecasts & Ranking")
    st.caption(
        "Wave 6: deterministic pre-trade forecasts (expected return proxy), star rating (1–5) and ranking. "
        "Browse available forecast snapshots over time and inspect realized outcomes (when available)."
    )

    with st.sidebar:
        st.header("Artifacts")
        reports_dir = Path(st.text_input("reports/ directory", value=str(DEFAULT_REPORTS)))
        if not reports_dir.is_absolute():
            reports_dir = (ROOT / reports_dir).resolve()

        browse_history = st.checkbox("Browse timeline", value=True)
        refresh = st.button("Refresh", use_container_width=True)

        st.divider()
        top_n = st.number_input("Top N", min_value=1, max_value=500, value=50, step=10)

        st.divider()
        st.header("Outcomes (optional)")
        db_path = Path(st.text_input("DuckDB path", value=str(DEFAULT_DB)))
        if not db_path.is_absolute():
            db_path = (ROOT / db_path).resolve()
        show_outcomes_cols = st.checkbox("Show outcome columns", value=False)

    @st.cache_data(show_spinner=False)
    def _load_latest(_reports_dir: str) -> dict:
        return _read_latest_json(Path(_reports_dir))

    @st.cache_data(show_spinner=False)
    def _load_snapshots(_reports_dir: str) -> list[dict]:
        return _list_forecast_json_snapshots(Path(_reports_dir))

    @st.cache_data(show_spinner=False)
    def _load_obj(_path: str) -> dict:
        return _read_json(Path(_path))

    if refresh:
        _load_latest.clear()
        _load_snapshots.clear()
        _load_obj.clear()

    obj: dict = {}
    loaded_from = ""

    if browse_history:
        snaps = _load_snapshots(str(reports_dir))
        if snaps:
            # Group by asof_date
            by_date: dict[str, list[dict]] = {}
            for s in snaps:
                by_date.setdefault(s["asof_date"], []).append(s)
            dates_sorted = sorted(by_date.keys())

            if len(dates_sorted) >= 2:
                sel_date = st.select_slider(
                    "As-of date", options=dates_sorted, value=dates_sorted[-1]
                )
            else:
                # Streamlit's select_slider can throw a frontend RangeError when options has length 1.
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
            "No forecast artifacts found. Run `<PY> scripts/sentinel.py forecast` (Windows: `py`, Linux/macOS: `python`) or enable forecasts in certify "
            "(SENTINEL_ENABLE_FORECASTS=1)."
        )
        return

    meta = obj.get("meta") or {}
    diags = obj.get("diagnostics") or {}

    st.subheader("Run metadata")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("asof_date", str(meta.get("asof_date") or ""))
    c2.metric("universe", str(meta.get("universe_id") or ""))
    c3.metric("run_id", str(meta.get("run_id") or "(none)"))
    c4.metric("enterable", int(diags.get("enterable_total", 0) or 0))
    st.write(f"**code_fingerprint:** `{meta.get('code_fingerprint','')}`")
    if loaded_from:
        st.caption(f"Loaded: `{Path(loaded_from).name}`")

    rows = obj.get("rows") or []
    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("Forecast artifact exists but contains zero enterable rows for this as-of date.")
        return

    # Filters
    with st.sidebar:
        st.header("Filters")
        firms = sorted([x for x in df.get("firm", pd.Series(dtype=str)).dropna().unique().tolist()])
        ratings = sorted([x for x in df.get("rating", pd.Series(dtype=str)).dropna().unique().tolist()])
        min_stars = st.slider("Min stars", min_value=1, max_value=5, value=1)
        firm_sel = st.multiselect("Firm", firms, default=[])
        rating_sel = st.multiselect("Rating", ratings, default=[])
        ticker_query = st.text_input("Ticker contains", value="")

    fdf = df.copy()
    if firm_sel:
        fdf = fdf[fdf["firm"].isin(firm_sel)]
    if rating_sel:
        fdf = fdf[fdf["rating"].isin(rating_sel)]
    if "stars" in fdf.columns:
        fdf = fdf[pd.to_numeric(fdf["stars"], errors="coerce").fillna(0).astype(int) >= int(min_stars)]
    if ticker_query.strip():
        q = ticker_query.strip().upper()
        col = "ticker_effective" if "ticker_effective" in fdf.columns else "ticker"
        if col in fdf.columns:
            fdf = fdf[fdf[col].astype(str).str.upper().str.contains(q, na=False)]

    # Optional outcomes
    signal_d = _parse_date(str(meta.get("asof_date") or ""))
    tick_col = "ticker_effective" if "ticker_effective" in fdf.columns else "ticker"
    outcomes_df = pd.DataFrame()
    max_sig_date: date | None = None
    if signal_d is not None:
        tickers = sorted([x for x in fdf.get(tick_col, pd.Series(dtype=str)).dropna().unique().tolist()])
        outcomes_df, max_sig_date = _load_trade_outcomes(db_path=db_path, signal_date=signal_d, tickers=tickers)

    # Merge outcomes (left)
    if not outcomes_df.empty and tick_col in fdf.columns:
        fdf = fdf.merge(outcomes_df[["ticker", "trade_executed", "net_return_pct", "buy_date", "sell_date"]],
                        left_on=tick_col, right_on="ticker", how="left")
        fdf.drop(columns=["ticker"], inplace=True, errors="ignore")
    else:
        # Ensure columns exist for consistent rendering.
        for c in ("trade_executed", "net_return_pct", "buy_date", "sell_date"):
            if c not in fdf.columns:
                fdf[c] = None

    def _outcome_bucket(row: pd.Series) -> str:
        # Pending if the selected asof_date is after the last available audit_trades.signal_date.
        if signal_d is not None and max_sig_date is not None and signal_d > max_sig_date:
            return "pending"
        traded = bool(row.get("trade_executed") is True)
        if not traded:
            # If we have outcomes up to this date, but no trade row exists => no-trade.
            if signal_d is not None and max_sig_date is not None and signal_d <= max_sig_date:
                return "no_trade"
            return "pending"
        try:
            nr = float(row.get("net_return_pct"))
        except Exception:
            return "pending"
        return "gain" if nr > 0 else "loss"

    fdf["_outcome"] = fdf.apply(_outcome_bucket, axis=1)

    # Display
    st.subheader("Ranking")

    base_cols = [
        "rank",
        "stars",
        tick_col,
        "firm",
        "rating",
        "forecast_return_pct",
        "confidence",
        "sentiment_score",
        "headline",
    ]
    outcome_cols = ["trade_executed", "net_return_pct", "buy_date", "sell_date"]

    show_cols = [c for c in base_cols if c in fdf.columns]
    if show_outcomes_cols:
        show_cols = show_cols + [c for c in outcome_cols if c in fdf.columns]

    view = fdf[show_cols + ["_outcome"]].copy()

    # Stars rendering
    if "stars" in view.columns:
        view["stars"] = view["stars"].map(_stars)

    for c in ("forecast_return_pct", "confidence", "net_return_pct"):
        if c in view.columns:
            view[c] = pd.to_numeric(view[c], errors="coerce")

    view = view.sort_values(["rank"], ascending=[True], kind="mergesort").head(int(top_n))

    def _style_row(row: pd.Series) -> list[str]:
        """Return per-cell CSS styles for a single row.

        We color only the stars cell, based on the computed outcome bucket.
        """

        cols = list(row.index)
        out = ["" for _ in range(len(cols))]
        if "stars" not in cols:
            return out
        idx = cols.index("stars")
        bucket = str(row.get("_outcome") or "")
        if bucket == "gain":
            out[idx] = "color: #0b6e0b; font-weight: 700"
        elif bucket == "loss":
            out[idx] = "color: #b30000; font-weight: 700"
        elif bucket == "no_trade":
            out[idx] = "color: #6b7280"  # neutral gray
        else:  # pending
            out[idx] = "color: #c49a00; font-weight: 700"  # yellow-ish
        return out

    styled = view.style.apply(_style_row, axis=1)
    # Hide helper column while keeping it available to the row-style function.
    try:  # pandas>=1.4
        styled = styled.hide(axis="columns", subset=["_outcome"])
    except Exception:  # pragma: no cover
        pass

    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.caption(
        "Star colors: green=trade gain, red=trade loss, gray=no trade executed, yellow=pending/unknown outcome. "
        "Outcome coloring is derived from audit_trades.net_return_pct when a local DB is available."
    )

    st.divider()

    st.subheader("Drill-down")
    tickers_all = sorted([x for x in df.get(tick_col, pd.Series(dtype=str)).dropna().unique().tolist()])
    sel = st.selectbox("Select ticker", options=[""] + tickers_all)
    if sel:
        row = fdf[fdf[tick_col] == sel].head(1)
        if not row.empty:
            r = row.to_dict(orient="records")[0]
            left, right = st.columns([2, 1])
            with left:
                st.markdown(f"### {sel}")
                st.write(f"**firm:** {r.get('firm','')}")
                st.write(f"**rating:** {r.get('rating','')}")
                st.write(f"**headline:** {r.get('headline','')}")
                if r.get("source_url"):
                    st.write(f"**source_url:** {r.get('source_url')}")
            with right:
                st.metric("stars", _stars(r.get("stars")))
                try:
                    st.metric("forecast_return_pct", f"{float(r.get('forecast_return_pct', 0.0)):.2f}")
                except Exception:
                    st.metric("forecast_return_pct", str(r.get("forecast_return_pct", "")))
                try:
                    st.metric("confidence", f"{float(r.get('confidence', 0.0)):.2f}")
                except Exception:
                    st.metric("confidence", str(r.get("confidence", "")))

            # Outcome details (if any)
            bucket = str(r.get("_outcome") or "")
            if bucket in ("gain", "loss", "no_trade", "pending"):
                with st.expander("Outcome details"):
                    st.write(
                        {
                            "outcome_bucket": bucket,
                            "trade_executed": r.get("trade_executed"),
                            "net_return_pct": r.get("net_return_pct"),
                            "buy_date": str(r.get("buy_date") or ""),
                            "sell_date": str(r.get("sell_date") or ""),
                        }
                    )

            with st.expander("Explainability (components)"):
                st.write(
                    {
                        "shrunk_return_pct": r.get("shrunk_return_pct"),
                        "sentiment_adj": r.get("sentiment_adj"),
                        "calibration_n": r.get("calibration_n"),
                        "calibration_bucket_mean_return_pct": r.get("calibration_bucket_mean_return_pct"),
                        "calibration_firm_mean_return_pct": r.get("calibration_firm_mean_return_pct"),
                        "calibration_global_mean_return_pct": r.get("calibration_global_mean_return_pct"),
                    }
                )


if st is not None:  # pragma: no cover
    render()
