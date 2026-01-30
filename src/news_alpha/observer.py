from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .db import connect_db, get_table_columns, resolve_recs_sentiment_column, table_exists
from .run import FIRM


@dataclass(frozen=True)
class Issue:
    severity: str  # OK|WARN|FAIL
    code: str
    message: str


def _parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    # Try JSON first
    if line.startswith("{") and line.endswith("}"):
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "event" in obj:
                return obj
        except Exception:
            return None
    # Fallback: key=value format
    parts = line.split()
    obj: Dict[str, Any] = {}
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        obj[k] = v
    if "event" in obj:
        return obj
    return None


def _load_events(log_file: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with log_file.open("r", encoding="utf-8") as f:
        for line in f:
            ev = _parse_log_line(line)
            if ev:
                events.append(ev)
    return events


def _rating_ok(score: float, rating: str) -> bool:
    if score >= 0.20:
        return rating == "BUY"
    if score <= -0.20:
        return rating == "DOWNGRADE"
    return rating == "HOLD"


def observe(db_path: str, *, log_file: Optional[str] = None) -> Tuple[str, List[Issue]]:
    issues: List[Issue] = []

    # 1) Basic DB contract checks
    con = connect_db(db_path)
    try:
        if not table_exists(con, "recs"):
            return "FAIL", [Issue("FAIL", "MISSING_TABLE_RECS", "Missing required table: recs")]
        if not table_exists(con, "sentiment_cache"):
            return "FAIL", [Issue("FAIL", "MISSING_TABLE_SENTIMENT_CACHE", "Missing required table: sentiment_cache")]

        rec_cols = get_table_columns(con, "recs").columns
        required = {"firm", "rating"}
        missing = sorted(required - set(rec_cols))
        if missing:
            return "FAIL", [Issue("FAIL", "RECS_SCHEMA", f"recs missing required columns: {missing}")]

        score_col = resolve_recs_sentiment_column(rec_cols)
        if not score_col:
            return "FAIL", [
                Issue(
                    "FAIL",
                    "RECS_SCHEMA",
                    "recs is missing a sentiment score column (expected one of: sentiment_score, sentiment, score)",
                )
            ]

        # Fetch all NEWS-ALPHA recs.
        recs = con.execute(
            f"SELECT rating, {score_col} FROM recs WHERE firm = ?",
            [FIRM],
        ).fetchall()

        if len(recs) == 0:
            issues.append(Issue("WARN", "NO_RECS", "No recs rows found for firm=NEWS-ALPHA"))
        else:
            bad_bounds = 0
            bad_rating = 0
            for rating, score in recs:
                s = float(score)
                if s < -1.0 or s > 1.0:
                    bad_bounds += 1
                if not _rating_ok(s, str(rating)):
                    bad_rating += 1

            if bad_bounds:
                issues.append(
                    Issue(
                        "FAIL",
                        "SCORE_OUT_OF_BOUNDS",
                        f"Found {bad_bounds} recs rows with sentiment_score outside [-1,+1]",
                    )
                )
            if bad_rating:
                issues.append(
                    Issue(
                        "FAIL",
                        "RATING_MISMATCH",
                        f"Found {bad_rating} recs rows where rating does not match score thresholds",
                    )
                )

        # 2) Log-based checks (optional)
        if log_file:
            lf = Path(log_file)
            if lf.exists():
                events = _load_events(lf)
                present = {str(e.get("event")) for e in events}
                for must in ("NEWS_ALPHA_START", "NEWS_ALPHA_SUMMARY"):
                    if must not in present:
                        issues.append(Issue("WARN", "MISSING_LOG_EVENT", f"Expected log event not found: {must}"))
            else:
                issues.append(Issue("WARN", "LOG_FILE_MISSING", f"Log file not found: {log_file}"))

    finally:
        con.close()

    # Verdict
    verdict = "OK"
    if any(i.severity == "FAIL" for i in issues):
        verdict = "FAIL"
    elif any(i.severity == "WARN" for i in issues):
        verdict = "WARN"
    return verdict, issues


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="news-alpha-observer")
    p.add_argument("--db", required=True, help="Path to DuckDB database")
    p.add_argument("--log-file", help="Optional log file to validate")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    verdict, issues = observe(args.db, log_file=args.log_file)

    print(verdict)
    for iss in issues:
        print(f"{iss.severity}: {iss.code} - {iss.message}")

    if verdict == "OK":
        return 0
    if verdict == "WARN":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
