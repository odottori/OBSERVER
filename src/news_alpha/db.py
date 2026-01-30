from __future__ import annotations

import duckdb
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: List[str]


def connect_db(db_path: str) -> duckdb.DuckDBPyConnection:
    # DuckDB uses a file path, ":memory:" is also allowed.
    return duckdb.connect(db_path)


def table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    q = """
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema='main' AND table_name = ?
    LIMIT 1
    """
    return con.execute(q, [table_name]).fetchone() is not None


def get_table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> TableInfo:
    rows = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    cols = [r[1] for r in rows]  # (cid, name, type, notnull, dflt_value, pk)
    return TableInfo(name=table_name, columns=cols)


def fetch_universe_tickers(
    con: duckdb.DuckDBPyConnection,
    universe_id: str,
    date_from: date,
    date_to: date,
) -> Set[str]:
    if not table_exists(con, "universe_membership"):
        raise RuntimeError("Missing required table: universe_membership")

    q = """
    SELECT DISTINCT ticker
    FROM universe_membership
    WHERE universe_id = ?
      AND start_date <= ?
      AND (end_date IS NULL OR end_date >= ?)
    """
    rows = con.execute(q, [universe_id, date_to, date_from]).fetchall()
    return {str(r[0]) for r in rows if r and r[0] is not None}


def _build_insert_sql(table: str, cols: Sequence[str]) -> str:
    cols_sql = ",".join(cols)
    placeholders = ",".join(["?"] * len(cols))
    return f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})"


def _filter_row_to_columns(row: Dict[str, Any], cols: List[str]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k in cols}


def _required_columns_present(cols: List[str], required: Sequence[str], table: str) -> None:
    missing = [c for c in required if c not in cols]
    if missing:
        raise RuntimeError(f"Table {table} is missing required columns: {missing}")


def _first_present(cols: List[str], candidates: Sequence[str]) -> str | None:
    """Return the first column name from *candidates* that exists in *cols*.

    This is used to support minor schema variations across SENTINEL-ALPHA
    repositories (e.g., `sentiment` vs `sentiment_score`).
    """

    for c in candidates:
        if c in cols:
            return c
    return None


def resolve_sentiment_cache_score_column(cols: List[str]) -> str | None:
    # Preferred canonical name first.
    return _first_present(cols, ["sentiment_score", "sentiment", "score", "value"])


def resolve_recs_sentiment_column(cols: List[str]) -> str | None:
    # Preferred canonical name first.
    return _first_present(cols, ["sentiment_score", "sentiment", "score"])


def existing_recs_keys(
    con: duckdb.DuckDBPyConnection,
    date_from: date,
    date_to: date,
    firm: str,
) -> Set[Tuple[str, str]]:
    if not table_exists(con, "recs"):
        raise RuntimeError("Missing required table: recs")

    cols = get_table_columns(con, "recs").columns
    _required_columns_present(cols, ["date", "ticker", "firm"], "recs")

    q = """
    SELECT date, ticker
    FROM recs
    WHERE firm = ? AND date BETWEEN ? AND ?
    """
    rows = con.execute(q, [firm, date_from, date_to]).fetchall()
    out: Set[Tuple[str, str]] = set()
    for d, t in rows:
        out.add((str(d), str(t)))
    return out


def write_recs(
    con: duckdb.DuckDBPyConnection,
    rec_rows: List[Dict[str, Any]],
    *,
    overwrite: bool,
    date_from: date,
    date_to: date,
    firm: str,
) -> int:
    if not rec_rows:
        return 0

    if not table_exists(con, "recs"):
        raise RuntimeError("Missing required table: recs")

    ti = get_table_columns(con, "recs")
    _required_columns_present(ti.columns, ["date", "ticker", "firm", "rating"], "recs")
    recs_sentiment_col = resolve_recs_sentiment_column(ti.columns)
    if not recs_sentiment_col:
        raise RuntimeError(
            "Table recs is missing a sentiment score column. Expected one of: "
            "sentiment_score, sentiment, score. Found columns: "
            f"{sorted(ti.columns)}"
        )

    if overwrite:
        con.execute(
            "DELETE FROM recs WHERE firm = ? AND date BETWEEN ? AND ?",
            [firm, date_from, date_to],
        )

    existing = set()
    if not overwrite:
        existing = existing_recs_keys(con, date_from, date_to, firm)

    filtered_rows: List[Dict[str, Any]] = []
    for r in rec_rows:
        # Support schema variations where the score column isn't named 'sentiment_score'.
        if recs_sentiment_col != "sentiment_score" and "sentiment_score" in r and recs_sentiment_col not in r:
            r = dict(r)
            r[recs_sentiment_col] = r.get("sentiment_score")
        key = (str(r.get("date")), str(r.get("ticker")))
        if not overwrite and key in existing:
            continue
        filtered_rows.append(_filter_row_to_columns(r, ti.columns))

    if not filtered_rows:
        return 0

    # Deterministic column order.
    cols = [c for c in ["date", "ticker", "firm", "rating", recs_sentiment_col, "headline", "source_url", "published_at"] if c in ti.columns]
    # Also include any other columns present in the row dicts (stable ordering).
    extra_cols = sorted({k for r in filtered_rows for k in r.keys()} - set(cols))
    cols = cols + extra_cols

    sql = _build_insert_sql("recs", cols)
    params = [[r.get(c) for c in cols] for r in filtered_rows]
    con.executemany(sql, params)
    return len(params)


def existing_sentiment_hashes(
    con: duckdb.DuckDBPyConnection,
    hashes: Sequence[str],
    model: str,
) -> Set[str]:
    if not hashes:
        return set()

    if not table_exists(con, "sentiment_cache"):
        raise RuntimeError("Missing required table: sentiment_cache")

    cols = get_table_columns(con, "sentiment_cache").columns
    _required_columns_present(cols, ["text_hash", "model"], "sentiment_cache")

    # DuckDB doesn't support parameterizing IN with a single list; use VALUES.
    placeholders = ",".join(["(?)"] * len(hashes))
    q = f"""
    SELECT sc.text_hash
    FROM sentiment_cache sc
    JOIN (VALUES {placeholders}) v(text_hash) ON sc.text_hash = v.text_hash
    WHERE sc.model = ?
    """
    rows = con.execute(q, [*hashes, model]).fetchall()
    return {str(r[0]) for r in rows if r and r[0] is not None}


def read_sentiment_scores(
    con: duckdb.DuckDBPyConnection,
    hashes: Sequence[str],
    model: str,
) -> Dict[str, float]:
    if not hashes:
        return {}

    cols = get_table_columns(con, "sentiment_cache").columns
    _required_columns_present(cols, ["text_hash", "model"], "sentiment_cache")
    score_col = resolve_sentiment_cache_score_column(cols)
    if not score_col:
        raise RuntimeError(
            "Table sentiment_cache is missing a sentiment score column. Expected one of: "
            "sentiment_score, sentiment, score, value. Found columns: "
            f"{sorted(cols)}"
        )

    placeholders = ",".join(["(?)"] * len(hashes))
    q = f"""
    SELECT sc.text_hash, sc.{score_col}
    FROM sentiment_cache sc
    JOIN (VALUES {placeholders}) v(text_hash) ON sc.text_hash = v.text_hash
    WHERE sc.model = ?
    """
    rows = con.execute(q, [*hashes, model]).fetchall()
    return {str(h): float(s) for (h, s) in rows}


def write_sentiment_cache(
    con: duckdb.DuckDBPyConnection,
    cache_rows: List[Dict[str, Any]],
    *,
    overwrite: bool,
    model: str,
) -> int:
    if not cache_rows:
        return 0

    if not table_exists(con, "sentiment_cache"):
        raise RuntimeError("Missing required table: sentiment_cache")

    ti = get_table_columns(con, "sentiment_cache")
    _required_columns_present(ti.columns, ["text_hash", "model"], "sentiment_cache")
    score_col = resolve_sentiment_cache_score_column(ti.columns)
    if not score_col:
        raise RuntimeError(
            "Table sentiment_cache is missing a sentiment score column. Expected one of: "
            "sentiment_score, sentiment, score, value. Found columns: "
            f"{sorted(ti.columns)}"
        )

    # De-dup by (text_hash, model) in input.
    seen: Set[Tuple[str, str]] = set()
    unique_rows: List[Dict[str, Any]] = []
    for r in cache_rows:
        key = (str(r.get("text_hash")), str(r.get("model")))
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(r)

    hashes = [str(r["text_hash"]) for r in unique_rows]

    if overwrite:
        # Delete only those hashes for this model.
        placeholders = ",".join(["(?)"] * len(hashes))
        q = f"""
        DELETE FROM sentiment_cache
        WHERE model = ? AND text_hash IN (SELECT text_hash FROM (VALUES {placeholders}) v(text_hash))
        """
        con.execute(q, [model, *hashes])
        existing = set()
    else:
        existing = existing_sentiment_hashes(con, hashes, model)

    filtered_rows = [r for r in unique_rows if str(r.get("text_hash")) not in existing]
    if not filtered_rows:
        return 0

    # Support schema variations where the score column isn't named 'sentiment_score'.
    for r in filtered_rows:
        if score_col != "sentiment_score" and "sentiment_score" in r and score_col not in r:
            r[score_col] = r.get("sentiment_score")

    # Drop any keys that are not actual columns in the target table (important for schema variations).
    filtered_rows = [_filter_row_to_columns(r, ti.columns) for r in filtered_rows]

    cols = [c for c in ["text_hash", "model", score_col, "text"] if c in ti.columns]
    extra_cols = sorted(({k for r in filtered_rows for k in r.keys()} - set(cols)) & set(ti.columns))
    cols = cols + extra_cols

    sql = _build_insert_sql("sentiment_cache", cols)
    params = [[r.get(c) for c in cols] for r in filtered_rows]
    con.executemany(sql, params)
    return len(params)
