"""Database status / health snapshot.

Usage:
    <PY> -m src.tools.db_status --db data/sentinel_alpha.db

Notes:
    This is the canonical module name (stdlib-only wrapper around basic DuckDB
    introspection). The repository intentionally avoids legacy/misnamed tool
    entrypoints.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_db_path(db_path: str) -> str:
    p = Path(db_path)
    if p.is_absolute():
        return str(p)
    return str((_project_root() / p).resolve())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="db_status", description="SENTINEL-ALPHA DB status")
    ap.add_argument(
        "--db",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    import duckdb

    db_path = _normalize_db_path(args.db_path)
    con = duckdb.connect(db_path)
    try:
        tables = con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='main'
            ORDER BY table_name
            """
        ).fetchall()

        print(f"DB: {db_path}")
        print(f"Tables: {len(tables)}")

        try:
            max_req = con.execute("SELECT max(requested_at) FROM data_gaps").fetchone()[0]
            print(f"Last data_gaps.requested_at: {max_req}")
        except Exception:
            print("Last data_gaps.requested_at: (table missing)")

        try:
            df = con.execute(
                """
                SELECT coalesce(source,'(null)') AS source, count(*) AS n
                FROM prices
                GROUP BY 1
                ORDER BY n DESC
                LIMIT 5
                """
            ).fetchdf()
            print(df)
        except Exception:
            print("Prices breakdown: (table missing)")
    finally:
        con.close()


if __name__ == "__main__":
    main()
