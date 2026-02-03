from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.phase0.core.ticker_normalize import normalize_ticker_sql
from src.phase0.db.audit_store import compute_code_fingerprint


# --- Spec constants (WAVE6_FORECAST_STARS_RANKING_SPEC.md v0.1) ---
SPEC_NAME = "WAVE6_FORECAST_STARS_RANKING_SPEC.md"
SPEC_VERSION = "v0.1"

N_MIN = 20
N_CONF = 60
W_GLOBAL = 0.25
K_SENT = 0.20

DEFAULT_TOP_N = 25
DEFAULT_EXCLUDE_EXIT_REASON = "FALLBACK_LAST_PRICE"


def determine_asof_date(con: duckdb.DuckDBPyConnection, universe_id: str) -> date | None:
    """Return the max(recs.date) for the selected universe."""
    uid = (universe_id or "ALL").strip() or "ALL"
    if uid.upper() == "ALL":
        row = con.execute("SELECT MAX(date) FROM recs").fetchone()
    else:
        row = con.execute("SELECT MAX(date) FROM recs WHERE universe_id = ?", [uid]).fetchone()
    if not row:
        return None
    return row[0]


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _iso(x) -> str | None:
    if x is None:
        return None
    if isinstance(x, date):
        return x.isoformat()
    try:
        return str(x)
    except Exception:
        return None


def _stable_sort(df: pd.DataFrame, cols: list[str], ascending: list[bool]) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df.sort_values(cols, ascending=ascending, kind="mergesort").reset_index(drop=True)


def load_candidate_signals(
    con: duckdb.DuckDBPyConnection,
    universe_id: str,
    asof_date: date,
) -> pd.DataFrame:
    """Load *eligible* candidate signals for the asof_date (includes right-censored/missing prices).

    Eligibility matches the audit engine gate semantics:
    - ticker normalization + ticker_mappings
    - survivorship filtering via universe_membership
    - conservative enterability diagnostic via prices MIN(date) > signal_date
    """

    uid = (universe_id or "ALL").strip() or "ALL"

    # Conservative ticker canonicalization (DOT for class shares).
    r_base = "upper(trim(rt.ticker))"
    r_norm = normalize_ticker_sql("rt.ticker")
    um_norm = normalize_ticker_sql("um.ticker")
    tmr_alias_norm = normalize_ticker_sql("tmr.alias_ticker")
    tmr_can_norm = normalize_ticker_sql("tmr.canonical_ticker")
    tmu_alias_norm = normalize_ticker_sql("tmu.alias_ticker")
    tmu_can_norm = normalize_ticker_sql("tmu.canonical_ticker")

    sql = f"""
    WITH recs_today AS (
        SELECT *
        FROM recs rt
        WHERE rt.date = ?
          AND (? = 'ALL' OR rt.universe_id = ?)
    ),
    recs_mapped AS (
        SELECT
            rt.date AS signal_date,
            rt.ticker AS ticker_original,
            {r_norm} AS ticker_normalized,
            COALESCE({tmr_can_norm}, {r_norm}) AS ticker,
            CASE WHEN ({r_base} != rt.ticker OR {r_norm} != {r_base}) THEN 1 ELSE 0 END AS normalization_changed,
            CASE WHEN tmr.canonical_ticker IS NOT NULL THEN 1 ELSE 0 END AS mapping_applied,
            rt.firm,
            rt.rating,
            rt.sentiment_score,
            rt.headline,
            rt.source_url,
            rt.universe_id
        FROM recs_today rt
        LEFT JOIN ticker_mappings tmr
          ON {tmr_alias_norm} = {r_norm}
         AND (tmr.start_date IS NULL OR rt.date >= tmr.start_date)
         AND (tmr.end_date IS NULL OR rt.date <= tmr.end_date)
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
            e.ticker AS ticker_effective,
            e.ticker_original,
            e.ticker_normalized,
            e.normalization_changed,
            e.mapping_applied,
            e.firm,
            e.rating,
            e.sentiment_score,
            e.headline,
            e.source_url,
            e.universe_id,
            ps.n_prices,
            ps.first_price_date,
            ps.last_price_date,
            (SELECT MIN(p.date) FROM prices p WHERE p.ticker = e.ticker AND p.date > e.signal_date) AS intended_buy_date
        FROM eligible e
        LEFT JOIN price_stats ps ON ps.ticker = e.ticker
    )
    SELECT *
    FROM elig_prices
    """

    # Parameter order: asof_date, universe_id (twice for recs filter), universe_id for membership join.
    return con.execute(sql, [asof_date, uid, uid, uid]).df()


def load_calibration_stats(
    con: duckdb.DuckDBPyConnection,
    asof_date: date,
    exclude_exit_reason: str | None = DEFAULT_EXCLUDE_EXIT_REASON,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Return (bucket_stats, firm_stats, global_stats) from audit_trades."""

    base_where = "WHERE signal_date < ? AND COALESCE(net_return_pct, gross_return_pct) IS NOT NULL"
    params: list[Any] = [asof_date]

    if exclude_exit_reason:
        base_where += " AND exit_reason <> ?"
        params.append(str(exclude_exit_reason))

    bucket_sql = (
        "SELECT firm, rating, COUNT(*) AS n, "
        "AVG(COALESCE(net_return_pct, gross_return_pct)) AS mean_return_pct, "
        "STDDEV_SAMP(COALESCE(net_return_pct, gross_return_pct)) AS stdev_return_pct, "
        "MAX(signal_date) AS last_signal_date "
        "FROM audit_trades "
        f"{base_where} "
        "GROUP BY firm, rating"
    )
    firm_sql = (
        "SELECT firm, COUNT(*) AS n, "
        "AVG(COALESCE(net_return_pct, gross_return_pct)) AS mean_return_pct "
        "FROM audit_trades "
        f"{base_where} "
        "GROUP BY firm"
    )
    global_sql = (
        "SELECT COUNT(*) AS n, AVG(COALESCE(net_return_pct, gross_return_pct)) AS mean_return_pct "
        "FROM audit_trades "
        f"{base_where}"
    )

    bucket_df = con.execute(bucket_sql, params).df()
    firm_df = con.execute(firm_sql, params).df()
    g_row = con.execute(global_sql, params).fetchone()
    g_n = int((g_row[0] or 0) if g_row else 0)
    try:
        g_mean = float(g_row[1]) if g_row and g_row[1] is not None else 0.0
    except Exception:
        g_mean = 0.0

    global_stats = {"n": float(g_n), "mean_return_pct": float(g_mean)}
    return bucket_df, firm_df, global_stats


def _compute_shrunk_return(
    bucket_mean: float,
    firm_mean: float,
    global_mean: float,
    n_bucket: int,
) -> float:
    # Step 4 (spec): shrink bucket mean toward firm mean when n < N_MIN
    if n_bucket >= N_MIN:
        shrunk = float(bucket_mean)
    else:
        alpha = float(n_bucket) / float(N_MIN)
        shrunk = float(bucket_mean) * alpha + float(firm_mean) * (1.0 - alpha)

        # Blend toward global mean; weight rises as n is small, floor=W_GLOBAL
        prior_weight = max(float(W_GLOBAL), 1.0 - alpha)
        shrunk = (1.0 - prior_weight) * shrunk + prior_weight * float(global_mean)
    return float(shrunk)


def _stars_by_percentile(idx0: int, n: int) -> int:
    if n <= 0:
        return 0
    # Percentile buckets: 5★ top 10%, 4★ next 20%, 3★ next 40%, 2★ next 20%, 1★ bottom 10%
    c5 = max(1, int(math.ceil(0.10 * n)))
    c4 = int(math.ceil(0.30 * n))
    c3 = int(math.ceil(0.70 * n))
    c2 = int(math.ceil(0.90 * n))
    if idx0 < c5:
        return 5
    if idx0 < c4:
        return 4
    if idx0 < c3:
        return 3
    if idx0 < c2:
        return 2
    return 1


def generate_forecast_ranking(
    con: duckdb.DuckDBPyConnection,
    universe_id: str = "ALL",
    asof_date: date | None = None,
    top_n: int = DEFAULT_TOP_N,
    run_id: str | None = None,
    exclude_exit_reason: str | None = DEFAULT_EXCLUDE_EXIT_REASON,
) -> dict[str, Any]:
    """Generate forecasts, stars and a deterministic ranking (JSON-serializable dict)."""

    uid = (universe_id or "ALL").strip() or "ALL"
    asof = asof_date or determine_asof_date(con, uid)
    if asof is None:
        raise ValueError("No recs rows found; cannot infer asof_date")

    candidates = load_candidate_signals(con, uid, asof)

    # Diagnostics (pre-enterable filter)
    candidates_total = int(len(candidates))
    missing_prices = int(candidates["n_prices"].isna().sum()) if candidates_total else 0
    right_censored = int(((~candidates["n_prices"].isna()) & (candidates["intended_buy_date"].isna())).sum()) if candidates_total else 0

    enterable = candidates
    if candidates_total:
        enterable = candidates.loc[(~candidates["n_prices"].isna()) & (~candidates["intended_buy_date"].isna())].copy()
    enterable_total = int(len(enterable))

    bucket_df, firm_df, global_stats = load_calibration_stats(con, asof, exclude_exit_reason=exclude_exit_reason)
    global_n = int(global_stats.get("n", 0.0) or 0)
    global_mean = float(global_stats.get("mean_return_pct", 0.0) or 0.0)

    # Index calibration stats for fast lookup
    bucket_map = {}
    for _, r in bucket_df.iterrows():
        key = (str(r.get("firm") or ""), str(r.get("rating") or ""))
        bucket_map[key] = {
            "n": int(r.get("n") or 0),
            "mean": float(r.get("mean_return_pct") or 0.0),
            "stdev": (float(r.get("stdev_return_pct")) if r.get("stdev_return_pct") is not None else None),
            "last_signal_date": r.get("last_signal_date"),
        }

    firm_map = {}
    for _, r in firm_df.iterrows():
        key = str(r.get("firm") or "")
        firm_map[key] = {
            "n": int(r.get("n") or 0),
            "mean": float(r.get("mean_return_pct") or 0.0),
        }

    rows: list[dict[str, Any]] = []
    if enterable_total == 0:
        # Still return a stable object for downstream consumers.
        out = {
            "meta": {
                "spec": SPEC_NAME,
                "spec_version": SPEC_VERSION,
                "universe_id": uid,
                "asof_date": asof.isoformat(),
                "run_id": run_id,
                "code_fingerprint": compute_code_fingerprint(),
            },
            "constants": {
                "N_MIN": N_MIN,
                "N_CONF": N_CONF,
                "W_GLOBAL": W_GLOBAL,
                "K_SENT": K_SENT,
                "exclude_exit_reason": exclude_exit_reason,
            },
            "diagnostics": {
                "candidates_total": candidates_total,
                "enterable_total": enterable_total,
                "dropped_missing_prices": missing_prices,
                "dropped_right_censored": right_censored,
                "calibration_global_n": global_n,
                "calibration_global_mean_return_pct": global_mean,
            },
            "rows": [],
            "by_firm": [],
        }
        return out

    # Compute per-signal forecasts
    for _, r in enterable.iterrows():
        firm = str(r.get("firm") or "")
        rating = str(r.get("rating") or "")
        key = (firm, rating)

        b = bucket_map.get(key)
        n_bucket = int(b.get("n") if b else 0)
        bucket_mean = float(b.get("mean") if b else 0.0)
        last_sig = b.get("last_signal_date") if b else None
        b_stdev = b.get("stdev") if b else None

        f = firm_map.get(firm)
        firm_mean = float(f.get("mean") if f else global_mean)
        if firm_mean is None:
            firm_mean = global_mean

        # If no bucket stats exist, use firm_mean as the bucket mean placeholder.
        if b is None:
            bucket_mean = firm_mean

        sentiment = r.get("sentiment_score")
        try:
            s = float(sentiment) if sentiment is not None else 0.0
        except Exception:
            s = 0.0
        s = _clamp(s, -1.0, 1.0)

        if global_n <= 0:
            # Spec fallback when there are no historical trades.
            shrunk = 0.0
            conf = 0.0
            sent_adj = s * 0.50
            forecast = sent_adj
        else:
            shrunk = _compute_shrunk_return(bucket_mean, firm_mean, global_mean, n_bucket)
            conf = min(1.0, float(n_bucket) / float(N_CONF))
            sent_adj = s * float(K_SENT)
            forecast = float(shrunk) + float(sent_adj)

        rows.append(
            {
                "signal_date": _iso(r.get("signal_date")),
                "intended_buy_date": _iso(r.get("intended_buy_date")),
                "ticker_original": str(r.get("ticker_original") or ""),
                "ticker_normalized": str(r.get("ticker_normalized") or ""),
                "ticker_effective": str(r.get("ticker_effective") or ""),
                "normalization_changed": int(r.get("normalization_changed") or 0),
                "mapping_applied": int(r.get("mapping_applied") or 0),
                "firm": firm,
                "rating": rating,
                "sentiment_score": float(s),
                "headline": str(r.get("headline") or ""),
                "source_url": str(r.get("source_url") or ""),
                "universe_id": str(r.get("universe_id") or uid),
                "calibration_n": int(n_bucket),
                "calibration_bucket_mean_return_pct": float(bucket_mean),
                "calibration_bucket_stdev_return_pct": (float(b_stdev) if b_stdev is not None else None),
                "calibration_bucket_last_signal_date": _iso(last_sig),
                "calibration_firm_mean_return_pct": float(firm_mean),
                "calibration_global_mean_return_pct": float(global_mean),
                "shrunk_return_pct": float(shrunk),
                "sentiment_adj": float(sent_adj),
                "forecast_return_pct": float(forecast),
                "confidence": float(conf),
            }
        )

    df = pd.DataFrame(rows)

    # Stars are assigned by percentile on forecast ordering (with deterministic tie-breakers).
    df = _stable_sort(
        df,
        cols=[
            "forecast_return_pct",
            "confidence",
            "rating",
            "firm",
            "ticker_effective",
        ],
        ascending=[False, False, False, True, True],
    )
    n = len(df)
    df["stars"] = [_stars_by_percentile(i, n) for i in range(n)]

    # Final ranking sort (spec step 7)
    df = _stable_sort(
        df,
        cols=[
            "stars",
            "forecast_return_pct",
            "confidence",
            "rating",
            "firm",
            "ticker_effective",
        ],
        ascending=[False, False, False, False, True, True],
    )
    df["rank"] = list(range(1, len(df) + 1))

    # Per-firm breakdown
    by_firm = (
        df.groupby("firm")
        .agg(
            n=("ticker_effective", "count"),
            avg_forecast_return_pct=("forecast_return_pct", "mean"),
            avg_stars=("stars", "mean"),
        )
        .reset_index()
    )
    by_firm = _stable_sort(by_firm, ["avg_stars", "avg_forecast_return_pct", "firm"], [False, False, True])

    out = {
        "meta": {
            "spec": SPEC_NAME,
            "spec_version": SPEC_VERSION,
            "universe_id": uid,
            "asof_date": asof.isoformat(),
            "run_id": run_id,
            "code_fingerprint": compute_code_fingerprint(),
        },
        "constants": {
            "N_MIN": N_MIN,
            "N_CONF": N_CONF,
            "W_GLOBAL": W_GLOBAL,
            "K_SENT": K_SENT,
            "exclude_exit_reason": exclude_exit_reason,
        },
        "diagnostics": {
            "candidates_total": candidates_total,
            "enterable_total": int(len(df)),
            "dropped_missing_prices": missing_prices,
            "dropped_right_censored": right_censored,
            "calibration_global_n": global_n,
            "calibration_global_mean_return_pct": global_mean,
        },
        "rows": df.to_dict(orient="records"),
        "by_firm": by_firm.to_dict(orient="records"),
    }
    return out


def _df_to_md(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "(none)"
    try:
        return df.to_markdown(index=False)
    except Exception:
        cols = list(df.columns)
        lines = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
        for row in df.itertuples(index=False):
            lines.append("|" + "|".join(str(x) for x in row) + "|")
        return "\n".join(lines)


def write_forecast_ranking_artifacts(
    obj: dict[str, Any],
    reports_dir: str | Path = "reports",
    run_id: str | None = None,
    asof_date: str | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, str]:
    """Write JSON + Markdown artifacts and update FORECAST_RANKING_LATEST.json.

    Returns a dict with the written paths.
    """

    rep = Path(reports_dir)
    rep.mkdir(parents=True, exist_ok=True)

    meta = obj.get("meta") or {}
    rid = (run_id or meta.get("run_id") or "").strip() or None
    asof = (asof_date or meta.get("asof_date") or "").strip() or None
    if not asof:
        raise ValueError("Missing asof_date for artifact naming")

    suffix = rid if rid else asof
    json_path = rep / f"FORECAST_RANKING_{suffix}.json"
    md_path = rep / f"FORECAST_RANKING_{suffix}.md"
    latest_json_path = rep / "FORECAST_RANKING_LATEST.json"

    # Stable JSON formatting (deterministic).
    json_path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    latest_json_path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")

    # Markdown report
    rows = obj.get("rows") or []
    df = pd.DataFrame(rows)
    if not df.empty:
        # Compact view for markdown.
        df2 = df[["rank", "stars", "ticker_effective", "firm", "rating", "forecast_return_pct", "confidence", "headline"]].copy()
        df2["forecast_return_pct"] = df2["forecast_return_pct"].map(lambda x: f"{float(x):.2f}")
        df2["confidence"] = df2["confidence"].map(lambda x: f"{float(x):.2f}")
        df2["stars"] = df2["stars"].map(lambda x: "★" * int(x))
        df2 = df2.head(max(0, int(top_n)))
    else:
        df2 = pd.DataFrame()

    by_firm = pd.DataFrame(obj.get("by_firm") or [])
    if not by_firm.empty:
        by_firm2 = by_firm[["firm", "n", "avg_forecast_return_pct", "avg_stars"]].copy()
        by_firm2["avg_forecast_return_pct"] = by_firm2["avg_forecast_return_pct"].map(lambda x: f"{float(x):.2f}")
        by_firm2["avg_stars"] = by_firm2["avg_stars"].map(lambda x: f"{float(x):.2f}")
    else:
        by_firm2 = pd.DataFrame()

    diagnostics = obj.get("diagnostics") or {}
    constants = obj.get("constants") or {}

    md_lines: list[str] = []
    md_lines.append("# SENTINEL-ALPHA: Pre-trade Forecasts & Ranking\n")
    md_lines.append(f"- universe_id: `{meta.get('universe_id')}`")
    md_lines.append(f"- asof_date: `{asof}`")
    if rid:
        md_lines.append(f"- run_id: `{rid}`")
    md_lines.append(f"- code_fingerprint: `{meta.get('code_fingerprint')}`\n")

    md_lines.append("## Diagnostics\n")
    for k in (
        "candidates_total",
        "enterable_total",
        "dropped_missing_prices",
        "dropped_right_censored",
        "calibration_global_n",
        "calibration_global_mean_return_pct",
    ):
        if k in diagnostics:
            md_lines.append(f"- {k}: `{diagnostics.get(k)}`")
    md_lines.append("")

    md_lines.append("## Constants\n")
    for k in ("N_MIN", "N_CONF", "W_GLOBAL", "K_SENT", "exclude_exit_reason"):
        if k in constants:
            md_lines.append(f"- {k}: `{constants.get(k)}`")
    md_lines.append("")

    md_lines.append(f"## Top {int(top_n)}\n")
    md_lines.append(_df_to_md(df2))
    md_lines.append("")

    md_lines.append("## By firm\n")
    md_lines.append(_df_to_md(by_firm2))
    md_lines.append("")

    md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    return {
        "json": str(json_path),
        "md": str(md_path),
        "latest_json": str(latest_json_path),
    }
