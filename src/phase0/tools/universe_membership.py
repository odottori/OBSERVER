"""Load / upsert historical universe membership into DuckDB.

Purpose
-------
`universe_membership` controls survivorship bias by letting SENTINEL-ALPHA decide
whether a ticker was eligible on a given signal date.

This tool is deliberately "data-source agnostic": it does not fetch anything from
the web. You provide the dataset (CSV or parquet) from your preferred source of truth.

Input schema
------------
Expected columns (CSV/parquet):
- universe_id (optional if --universe-id is provided)
- ticker
- start_date (YYYY-MM-DD)
- end_date   (YYYY-MM-DD or empty/null)
- source     (optional)
- notes      (optional)

Examples
--------
Load from CSV:
    <PY> -m src.tools.universe_membership --db data/sentinel_alpha.db --csv config/universe_membership.csv

Load the built-in example row:
    <PY> -m src.tools.universe_membership --db data/sentinel_alpha.db --example
"""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import duckdb

try:  # optional but strongly recommended for CSV/parquet
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore

from src.db.migrate import ensure_schema


def _default_db_path() -> str:
    return os.environ.get("SENTINEL_ALPHA_DB_PATH", os.path.join("data", "sentinel_alpha.db"))


def _parse_date(x) -> date | None:
    if x is None:
        return None
    if isinstance(x, date):
        return x
    s = str(x).strip()
    if not s or s.lower() in {"none", "null", "nat"}:
        return None
    # ISO 8601 date
    return date.fromisoformat(s[:10])


def _load_rows_from_df(
    df, universe_id_fallback: str | None, source_fallback: str, notes_fallback: str
) -> list[tuple]:
    cols = {c.lower(): c for c in df.columns}

    def col(name: str) -> str | None:
        return cols.get(name)

    universe_col = col("universe_id")
    ticker_col = col("ticker")
    start_col = col("start_date")
    end_col = col("end_date")
    source_col = col("source")
    notes_col = col("notes")

    if ticker_col is None or start_col is None:
        raise ValueError("Input must include at least columns: ticker, start_date")

    if universe_col is None and not universe_id_fallback:
        raise ValueError("Input is missing universe_id; provide --universe-id to supply a default.")

    rows: list[tuple] = []
    for _, r in df.iterrows():
        uid = (r[universe_col] if universe_col else universe_id_fallback)  # type: ignore[index]
        tick = r[ticker_col]
        sd = r[start_col]
        ed = r[end_col] if end_col else None
        src = r[source_col] if source_col else source_fallback
        nts = r[notes_col] if notes_col else notes_fallback

        uid = str(uid).strip()
        tick = str(tick).strip().upper()
        if not uid or not tick:
            continue

        sd2 = _parse_date(sd)
        if sd2 is None:
            raise ValueError(f"start_date is required (row universe_id={uid}, ticker={tick}).")

        ed2 = _parse_date(ed)
        rows.append((uid, tick, sd2, ed2, str(src).strip(), str(nts).strip()))
    return rows


def _load_rows_from_csv_or_parquet(
    path: Path, universe_id_fallback: str | None, source_fallback: str, notes_fallback: str
) -> list[tuple]:
    if pd is None:
        raise RuntimeError("pandas is required to load CSV/parquet inputs. Install requirements.txt first.")

    if not path.exists():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    return _load_rows_from_df(df, universe_id_fallback, source_fallback, notes_fallback)


def upsert_universe_membership(
    con: duckdb.DuckDBPyConnection,
    rows: Sequence[tuple],
) -> int:
    if not rows:
        return 0

    sql = """
    INSERT INTO universe_membership(universe_id, ticker, start_date, end_date, source, notes)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(universe_id, ticker, start_date) DO UPDATE SET
      end_date=excluded.end_date,
      source=excluded.source,
      notes=excluded.notes
    """

    for r in rows:
        con.execute(sql, list(r))
    return len(rows)


def _example_rows() -> list[tuple]:
    # Minimal, safe example. Replace with your licensed/official dataset.
    return [
        ("ALL", "AAPL", date(2010, 1, 1), None, "example", "Example membership row"),
    ]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="universe_membership", description="Load universe_membership into DuckDB")
    ap.add_argument("--db", dest="db_path", default=_default_db_path(), help="DuckDB path (default: data/sentinel_alpha.db)")
    ap.add_argument("--csv", dest="csv_path", default=None, help="Path to CSV/parquet file to load")
    ap.add_argument("--universe-id", dest="universe_id", default=None, help="Default universe_id when missing in the input file")
    ap.add_argument("--source", dest="source", default="user", help="Default source when missing in the input file")
    ap.add_argument("--notes", dest="notes", default="", help="Default notes when missing in the input file")
    ap.add_argument("--example", action="store_true", help="Load a minimal built-in example row (for smoke tests only)")
    args = ap.parse_args(argv)

    db_path = args.db_path
    con = duckdb.connect(db_path)
    try:
        ensure_schema(con)

        if args.example and not args.csv_path:
            rows = _example_rows()
        else:
            if not args.csv_path:
                raise SystemExit("ERROR: Provide --csv <PATH> (or use --example).")
            rows = _load_rows_from_csv_or_parquet(
                Path(args.csv_path), universe_id_fallback=args.universe_id, source_fallback=args.source, notes_fallback=args.notes
            )

        n = upsert_universe_membership(con, rows)
        print(f"[+] Loaded {n} universe_membership rows into: {db_path}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
