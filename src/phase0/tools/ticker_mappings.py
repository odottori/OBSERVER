"""Load / upsert time-bounded ticker mappings into DuckDB.

Purpose
-------
`ticker_mappings` normalizes symbol changes / corporate actions so that both:
- historical universe membership, and
- incoming signals

can be evaluated against a canonical ticker used by your price providers.

This tool is deliberately "data-source agnostic": it does not fetch anything from
the web. You provide the dataset (CSV or parquet).

Input schema
------------
Expected columns (CSV/parquet):
- alias_ticker
- canonical_ticker
- start_date (YYYY-MM-DD)
- end_date   (YYYY-MM-DD or empty/null)
- source     (optional)
- notes      (optional)

Examples
--------
Load from CSV:
    <PY> -m src.tools.ticker_mappings --db data/sentinel_alpha.db --csv config/ticker_mappings.csv

Load the built-in example row:
    <PY> -m src.tools.ticker_mappings --db data/sentinel_alpha.db --example
"""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path
from typing import Sequence

import duckdb

try:  # optional but strongly recommended for CSV/parquet
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore

from src.db.migrate import ensure_schema
from src.phase0.core.ticker_normalize import normalize_ticker


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
    return date.fromisoformat(s[:10])


def _load_rows_from_df(df, source_fallback: str, notes_fallback: str) -> list[tuple]:
    cols = {c.lower(): c for c in df.columns}

    def col(name: str) -> str | None:
        return cols.get(name)

    alias_col = col("alias_ticker")
    canon_col = col("canonical_ticker")
    start_col = col("start_date")
    end_col = col("end_date")
    source_col = col("source")
    notes_col = col("notes")

    if alias_col is None or canon_col is None or start_col is None:
        raise ValueError("Input must include columns: alias_ticker, canonical_ticker, start_date")

    rows: list[tuple] = []
    for _, r in df.iterrows():
        alias = normalize_ticker(r[alias_col])
        canon = normalize_ticker(r[canon_col])
        if not alias or not canon:
            continue

        sd = _parse_date(r[start_col])
        if sd is None:
            raise ValueError(f"start_date is required (row alias_ticker={alias}).")

        ed = _parse_date(r[end_col]) if end_col else None
        src = r[source_col] if source_col else source_fallback
        nts = r[notes_col] if notes_col else notes_fallback

        rows.append((alias, canon, sd, ed, str(src).strip(), str(nts).strip()))
    return rows


def _load_rows_from_csv_or_parquet(path: Path, source_fallback: str, notes_fallback: str) -> list[tuple]:
    if pd is None:
        raise RuntimeError("pandas is required to load CSV/parquet inputs. Install requirements.txt first.")

    if not path.exists():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    return _load_rows_from_df(df, source_fallback, notes_fallback)


def upsert_ticker_mappings(con: duckdb.DuckDBPyConnection, rows: Sequence[tuple]) -> int:
    if not rows:
        return 0

    sql = """
    INSERT INTO ticker_mappings(alias_ticker, canonical_ticker, start_date, end_date, source, notes)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(alias_ticker, start_date) DO UPDATE SET
      canonical_ticker=excluded.canonical_ticker,
      end_date=excluded.end_date,
      source=excluded.source,
      notes=excluded.notes
    """

    for r in rows:
        con.execute(sql, list(r))
    return len(rows)


def _example_rows() -> list[tuple]:
    return [
        ("FB", "META", date(2012, 5, 18), date(2021, 10, 27), "example", "Facebook -> Meta symbol change"),
    ]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ticker_mappings", description="Load ticker_mappings into DuckDB")
    ap.add_argument("--db", dest="db_path", default=_default_db_path(), help="DuckDB path (default: data/sentinel_alpha.db)")
    ap.add_argument("--csv", dest="csv_path", default=None, help="Path to CSV/parquet file to load")
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
            rows = _load_rows_from_csv_or_parquet(Path(args.csv_path), source_fallback=args.source, notes_fallback=args.notes)

        n = upsert_ticker_mappings(con, rows)
        print(f"[+] Loaded {n} ticker_mappings rows into: {db_path}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
