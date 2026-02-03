"""Strict provenance gate (no test data).

Purpose
-------
Fail fast if any signal row in `recs` is missing minimum provenance or uses placeholder/test URLs.
This is intended to prevent "fixtures" or synthetic signals from becoming decision-grade.

Minimum provenance (required)
----------------------------
- headline: non-empty
- source_url: non-empty, http(s)
- published_at: non-null

Placeholder URL denylist (default: FAIL)
---------------------------------------
- example.* domains (e.g., example.com, www.example.org)
- localhost / 127.0.0.1 / 0.0.0.0

Usage
-----
<PY> -m src.tools.verify_provenance --db data/sentinel_alpha.db --universe-id ALL

Multi-OS:
- Windows/PowerShell: <PY> := `py -3.14` (or `py`)
- Linux/macOS:        <PY> := `python`

Exit codes
----------
0 PASS
1 FAIL (gate violated)
2 ERROR (unexpected failure)
"""

from __future__ import annotations

import argparse
import sys

import duckdb


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="verify_provenance", description="Strict provenance gate for recs")
    p.add_argument("--db", "--db-path", dest="db_path", default="data/sentinel_alpha.db", help="Path to DuckDB db")
    p.add_argument("--universe-id", default="ALL", help="Universe id to validate (default: ALL)")
    p.add_argument("--firm", default="", help="If set, validate only this firm (exact match)")
    p.add_argument("--date-from", default="", help="Optional lower bound (YYYY-MM-DD) on recs.date")
    p.add_argument("--date-to", default="", help="Optional upper bound (YYYY-MM-DD) on recs.date")
    p.add_argument("--sample-limit", type=int, default=20, help="Sample size for failure diagnostics")
    p.add_argument(
        "--allow-placeholder-domains",
        action="store_true",
        default=False,
        help="Allow placeholder/test URL domains (NOT recommended; intended for test/dev DBs)",
    )
    return p.parse_args(argv)


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    q = "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?"
    try:
        return int(con.execute(q, [table]).fetchone()[0] or 0) > 0
    except Exception:
        return False


def _where_clause(args: argparse.Namespace) -> tuple[str, list]:
    where = ["1=1"]
    params: list = []

    uid = (args.universe_id or "").strip() or "ALL"
    if uid.upper() != "ALL":
        where.append("universe_id = ?")
        params.append(uid)

    firm = (args.firm or "").strip()
    if firm:
        where.append("firm = ?")
        params.append(firm)

    dfrom = (args.date_from or "").strip()
    if dfrom:
        where.append("date >= ?")
        params.append(dfrom)

    dto = (args.date_to or "").strip()
    if dto:
        where.append("date <= ?")
        params.append(dto)

    return " AND ".join(where), params


def main(argv: list[str] | None = None) -> None:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])
    sample_limit = max(0, int(args.sample_limit))

    con: duckdb.DuckDBPyConnection | None = None
    exit_code = 2

    # Regex is intentionally conservative: only reserved/example + local endpoints.
    placeholder_regex = (
        r"^https?://(www\.)?(example\.(com|org|net)|localhost)([:/]|$)"
        r"|^https?://(127\.0\.0\.1|0\.0\.0\.0)([:/]|$)"
    )

    try:
        con = duckdb.connect(database=args.db_path)

        if not _table_exists(con, "recs"):
            print("[FAIL] verify_provenance: missing required table 'recs'")
            exit_code = 1
        else:
            where_sql, params = _where_clause(args)

            total = int(con.execute(f"SELECT COUNT(*) FROM recs WHERE {where_sql}", params).fetchone()[0] or 0)

            # Missing minimum provenance.
            miss_q = f"""
            SELECT
                SUM(CASE WHEN headline IS NULL OR length(trim(headline)) = 0 THEN 1 ELSE 0 END) AS missing_headline,
                SUM(CASE WHEN source_url IS NULL OR length(trim(source_url)) = 0 THEN 1 ELSE 0 END) AS missing_source_url,
                SUM(CASE WHEN published_at IS NULL THEN 1 ELSE 0 END) AS missing_published_at
            FROM recs
            WHERE {where_sql}
            """
            mh, msu, mpa = con.execute(miss_q, params).fetchone()
            missing_headline = int(mh or 0)
            missing_source_url = int(msu or 0)
            missing_published_at = int(mpa or 0)

            # URL scheme + placeholder domain checks.
            url_q = f"""
            SELECT
                SUM(CASE WHEN source_url IS NOT NULL AND length(trim(source_url)) > 0
                         AND NOT (lower(trim(source_url)) LIKE 'http://%' OR lower(trim(source_url)) LIKE 'https://%')
                    THEN 1 ELSE 0 END) AS non_http_urls,
                SUM(CASE WHEN source_url IS NOT NULL AND length(trim(source_url)) > 0
                         AND regexp_matches(lower(trim(source_url)), '{placeholder_regex}')
                    THEN 1 ELSE 0 END) AS placeholder_urls
            FROM recs
            WHERE {where_sql}
            """
            non_http_urls, placeholder_urls = con.execute(url_q, params).fetchone()
            non_http_urls = int(non_http_urls or 0)
            placeholder_urls = int(placeholder_urls or 0)

            failures: list[str] = []
            if missing_headline > 0:
                failures.append(f"missing_headline={missing_headline}")
            if missing_source_url > 0:
                failures.append(f"missing_source_url={missing_source_url}")
            if missing_published_at > 0:
                failures.append(f"missing_published_at={missing_published_at}")
            if non_http_urls > 0:
                failures.append(f"non_http_urls={non_http_urls}")
            if (not args.allow_placeholder_domains) and placeholder_urls > 0:
                failures.append(f"placeholder_urls={placeholder_urls}")

            if failures:
                print("[FAIL] verify_provenance")
                print(f"  total_checked={total}")
                for f in failures:
                    print(f"  - {f}")

                # Sample diagnostic rows (best-effort).
                sample_where = where_sql
                sample_predicates = [
                    "headline IS NULL OR length(trim(headline)) = 0",
                    "source_url IS NULL OR length(trim(source_url)) = 0",
                    "published_at IS NULL",
                    "(source_url IS NOT NULL AND length(trim(source_url)) > 0 AND NOT (lower(trim(source_url)) LIKE 'http://%' OR lower(trim(source_url)) LIKE 'https://%'))",
                ]
                if not args.allow_placeholder_domains:
                    sample_predicates.append(
                        f"(source_url IS NOT NULL AND length(trim(source_url)) > 0 AND regexp_matches(lower(trim(source_url)), '{placeholder_regex}'))"
                    )

                sample_where = f"({sample_where}) AND (" + " OR ".join(sample_predicates) + ")"
                sample_sql = f"""
                SELECT date, ticker, firm,
                       CASE WHEN headline IS NULL THEN '' ELSE substr(headline, 1, 80) END AS headline_80,
                       source_url,
                       published_at
                FROM recs
                WHERE {sample_where}
                ORDER BY date DESC, firm, ticker
                LIMIT {sample_limit}
                """
                try:
                    rows = con.execute(sample_sql, params).fetchall()
                    if rows:
                        print("  sample:")
                        for r in rows:
                            d, t, firm, h, url, pub = r
                            print(f"    - {d} | {t} | {firm} | url={url} | published_at={pub} | headline={h}")
                except Exception:
                    pass

                exit_code = 1
            else:
                print("[PASS] verify_provenance")
                print(
                    f"  total_checked={total}; missing_headline={missing_headline}; missing_source_url={missing_source_url}; "
                    f"missing_published_at={missing_published_at}; non_http_urls={non_http_urls}; placeholder_urls={placeholder_urls}"
                )
                exit_code = 0

    except Exception as e:
        print("[ERROR] verify_provenance:", str(e))
        exit_code = 2
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
