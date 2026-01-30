from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .db import (
    connect_db,
    fetch_universe_tickers,
    read_sentiment_scores,
    table_exists,
    write_recs,
    write_sentiment_cache,
)
from .fixtures import RawNewsItem, load_fixtures_jsonl
from .logging_utils import LogConfig, configure_logger, log_event
from .sentiment import MODEL as SENTIMENT_MODEL, score_text

FIRM = "NEWS-ALPHA"
# Keep the DB sentiment_cache keyed by the sentiment module's declared model.
MODEL = SENTIMENT_MODEL


def normalize_ticker(raw: str) -> str:
    t = (raw or "").strip().upper()
    # Narrow class-share normalization: BRK-B -> BRK.B
    if len(t) >= 3 and "-" in t:
        import re

        if re.match(r"^[A-Z]{1,5}-[A-Z]$", t):
            t = t.replace("-", ".", 1)
    return t


def parse_yyyymmdd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_published_at(ts: str) -> datetime:
    """Parse ISO8601 timestamps deterministically.

    Accepts:
      - "2026-01-12T10:00:00Z"
      - "2026-01-12T10:00:00+00:00"
      - "2026-01-12 10:00:00" (treated as UTC)

    If timezone is missing, assume UTC.
    """

    t = ts.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        # Fallback common format
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def rating_from_score(score: float) -> str:
    if score >= 0.20:
        return "BUY"
    if score <= -0.20:
        return "DOWNGRADE"
    return "HOLD"


def write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    """Write JSONL (UTF-8) creating parent dirs."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def item_to_dict(it: "ScoredItem") -> Dict[str, Any]:
    return {
        "ticker": it.ticker,
        "published_at": it.published_at.isoformat() if it.published_at else None,
        "headline": it.headline,
        "source": it.source,
        "url": it.url,
        "body": it.body,
    }


def dedup_key(item: "ScoredItem") -> str:
    if item.url:
        return f"URL:{item.url}"
    # Fallback: hash(published_at|source|headline)
    base = f"{item.published_at_iso}|{item.source}|{item.headline}".strip()
    h = sha256(base.encode("utf-8")).hexdigest()
    return f"FALLBACK:{h}"


@dataclass(frozen=True)
class ScoredItem:
    ticker: str
    headline: str
    body: Optional[str]
    published_at: datetime
    published_at_iso: str
    source: str
    url: Optional[str]
    text_hash: str
    sentiment_score: float


def _choose_dedup_winner(a: ScoredItem, b: ScoredItem) -> ScoredItem:
    """Deterministic tie-breaker for dedup collisions."""

    def _score_key(x: ScoredItem) -> Tuple[int, str, str]:
        # Prefer longer text (headline+body) then lexicographic url then headline.
        text_len = len((x.headline or "")) + len((x.body or ""))
        url_key = x.url or ""
        return (text_len, url_key, x.headline)

    return max([a, b], key=_score_key)


def _choose_representative(items: List[ScoredItem]) -> ScoredItem:
    """Representative article: max abs(score), tie-break by lexicographic URL."""

    def _rep_key(x: ScoredItem) -> Tuple[float, str]:
        return (abs(x.sentiment_score), x.url or "")

    return max(items, key=_rep_key)


def _aggregate(items: List[ScoredItem]) -> Dict[Tuple[date, str], Dict[str, Any]]:
    grouped: Dict[Tuple[date, str], List[ScoredItem]] = {}
    for it in items:
        key = (it.published_at.date(), it.ticker)
        grouped.setdefault(key, []).append(it)

    out: Dict[Tuple[date, str], Dict[str, Any]] = {}
    for (d, t), group in grouped.items():
        mean_score = sum(x.sentiment_score for x in group) / float(len(group))
        mean_score = max(-1.0, min(1.0, mean_score))
        rep = _choose_representative(group)
        out[(d, t)] = {
            "date": d,
            "ticker": t,
            "firm": FIRM,
            "sentiment_score": mean_score,
            "rating": rating_from_score(mean_score),
            "headline": rep.headline,
            "source_url": rep.url,
            "published_at": rep.published_at,
        }
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="news-alpha")
    p.add_argument("--db", required=True, help="Path to DuckDB database")
    p.add_argument("--universe-id", required=True, help="Universe ID")
    p.add_argument("--date-from", required=True, help="YYYY-MM-DD")
    p.add_argument("--date-to", required=True, help="YYYY-MM-DD")

    p.add_argument("--fixtures", help="Path to JSONL fixtures")
    p.add_argument("--provider", default="fixtures", choices=["fixtures"], help="Provider (v0.1: fixtures only)")

    p.add_argument("--online", action="store_true", help="Enable online mode (guarded)")
    p.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing firm rows in date range")
    p.add_argument(
        "--rejects-file",
        default=None,
        help=(
            "Optional JSONL output path where rejected items are written "
            "(filtered by date/universe or dropped by dedup)."
        ),
    )

    p.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    p.add_argument("--log-json", action="store_true", help="Emit JSONL logs")
    p.add_argument("--log-file", help="Optional log file path")

    return p


def _offline_guard(online_requested: bool) -> None:
    if not online_requested:
        return
    allowed = os.getenv("NEWS_ALPHA_ALLOW_ONLINE", "0") == "1"
    if not allowed:
        raise SystemExit(
            "NEWS-ALPHA online mode is disabled. Set NEWS_ALPHA_ALLOW_ONLINE=1 and pass --online to enable."
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    run_id = str(uuid.uuid4())

    logger = configure_logger(LogConfig(level=args.log_level, json=args.log_json, file=args.log_file))

    log_event(
        logger,
        "NEWS_ALPHA_START",
        run_id=run_id,
        db=args.db,
        universe_id=args.universe_id,
        date_from=args.date_from,
        date_to=args.date_to,
        provider=args.provider,
        fixtures=args.fixtures,
        online_requested=bool(args.online),
        online_allowed=os.getenv("NEWS_ALPHA_ALLOW_ONLINE", "0") == "1",
        dry_run=bool(args.dry_run),
        overwrite=bool(args.overwrite),
    )

    try:
        _offline_guard(bool(args.online))
    except SystemExit as e:
        log_event(logger, "NEWS_ALPHA_OFFLINE_GUARD", level="ERROR", run_id=run_id, online_requested=True)
        raise

    date_from = parse_yyyymmdd(args.date_from)
    date_to = parse_yyyymmdd(args.date_to)
    if date_to < date_from:
        raise SystemExit("--date-to must be >= --date-from")

    # Optional sink for items rejected by filtering/dedup.
    rejects: List[Dict[str, Any]] = []

    if args.provider == "fixtures":
        if not args.fixtures:
            raise SystemExit("--fixtures is required when --provider=fixtures")
        fixtures_path = Path(args.fixtures)
        if not fixtures_path.exists():
            raise SystemExit(f"Fixtures not found: {fixtures_path}")

    con = connect_db(args.db)
    try:
        # Basic contract checks.
        for tname in ("recs", "sentiment_cache", "universe_membership"):
            if not table_exists(con, tname):
                raise SystemExit(f"Missing required table: {tname}")

        universe_raw = fetch_universe_tickers(con, args.universe_id, date_from, date_to)
        universe = {normalize_ticker(t) for t in universe_raw if normalize_ticker(t)}
        log_event(logger, "NEWS_ALPHA_UNIVERSE", run_id=run_id, universe_id=args.universe_id, tickers=len(universe))

        raw_items = list(load_fixtures_jsonl(args.fixtures))
        log_event(logger, "NEWS_ALPHA_LOAD_FIXTURES", run_id=run_id, fixtures=args.fixtures, lines=len(raw_items))

        expanded: List[Tuple[str, RawNewsItem]] = []
        for item in raw_items:
            for raw_ticker in item.tickers:
                nt = normalize_ticker(raw_ticker)
                if not nt:
                    continue
                expanded.append((nt, item))

        # Filter by universe and date range
        filtered: List[Tuple[str, RawNewsItem, datetime]] = []
        skipped_universe = 0
        skipped_date = 0
        for nt, item in expanded:
            if nt not in universe:
                skipped_universe += 1
                if args.rejects_file:
                    rejects.append(
                        {
                            "stage": "filter",
                            "reason": "universe",
                            "ticker": nt,
                            "published_at": item.published_at,
                            "source": item.source,
                            "headline": item.headline,
                            "url": item.url,
                            "body": item.body,
                        }
                    )
                continue
            dt = parse_published_at(item.published_at)
            d = dt.date()
            if d < date_from or d > date_to:
                skipped_date += 1
                if args.rejects_file:
                    rejects.append(
                        {
                            "stage": "filter",
                            "reason": "date_range",
                            "ticker": nt,
                            "published_at": item.published_at,
                            "published_at_parsed": dt.isoformat(),
                            "date_from": date_from.isoformat(),
                            "date_to": date_to.isoformat(),
                            "source": item.source,
                            "headline": item.headline,
                            "url": item.url,
                            "body": item.body,
                        }
                    )
                continue
            filtered.append((nt, item, dt))

        log_event(
            logger,
            "NEWS_ALPHA_FILTER",
            run_id=run_id,
            expanded=len(expanded),
            kept=len(filtered),
            skipped_universe=skipped_universe,
            skipped_date=skipped_date,
        )

        # Sentiment caching: read existing scores first.
        # Build normalized text + hash per item deterministically.
        texts: Dict[str, str] = {}
        for nt, item, dt in filtered:
            body = item.body
            combined = item.headline if not body else f"{item.headline}\n{body}"
            # score_text() already normalizes and hashes; reuse to avoid duplication.
            sr = score_text(item.headline, body)
            texts[sr.text_hash] = sr.normalized_text

        existing_scores = read_sentiment_scores(con, list(texts.keys()), MODEL)

        computed_cache_rows: List[Dict[str, Any]] = []
        scored_items: List[ScoredItem] = []

        # Score each item (from cache if available).
        for nt, item, dt in filtered:
            sr = score_text(item.headline, item.body)
            score = float(existing_scores.get(sr.text_hash, sr.score))
            if sr.text_hash not in existing_scores:
                computed_cache_rows.append(
                    {
                        "text_hash": sr.text_hash,
                        "model": MODEL,
                        "sentiment_score": score,
                        "text": sr.normalized_text,
                    }
                )

            scored_items.append(
                ScoredItem(
                    ticker=nt,
                    headline=item.headline,
                    body=item.body,
                    published_at=dt,
                    published_at_iso=dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    source=item.source,
                    url=item.url,
                    text_hash=sr.text_hash,
                    sentiment_score=score,
                )
            )

        log_event(
            logger,
            "NEWS_ALPHA_SENTIMENT",
            run_id=run_id,
            items=len(scored_items),
            cache_hits=len(existing_scores),
            cache_misses=len(computed_cache_rows),
        )

        # Dedup within run.
        deduped: Dict[str, ScoredItem] = {}
        dropped = 0
        for it in scored_items:
            k = dedup_key(it)
            if k in deduped:
                prev = deduped[k]
                winner = _choose_dedup_winner(prev, it)
                if winner is not prev:
                    log_event(
                        logger,
                        "NEWS_ALPHA_DEDUP_REPLACE",
                        run_id=run_id,
                        key=k,
                        old_url=prev.url,
                        new_url=it.url,
                    )
                    deduped[k] = winner
                if args.rejects_file:
                    dropped_item = it if winner is prev else prev
                    rejects.append(
                        {
                            "stage": "dedup",
                            "reason": "duplicate",
                            "key": k,
                            "winner_url": winner.url,
                            **item_to_dict(dropped_item),
                        }
                    )
                dropped += 1
                continue
            deduped[k] = it

        log_event(
            logger,
            "NEWS_ALPHA_DEDUP",
            run_id=run_id,
            before=len(scored_items),
            after=len(deduped),
            dropped=dropped,
        )

        # Aggregate to ticker-day.
        agg = _aggregate(list(deduped.values()))
        rec_rows = list(agg.values())

        # If the target `recs` table contains `universe_id`, populate it.
        # The DB writer will ignore the field for schemas that don't have it.
        for r in rec_rows:
            r.setdefault("universe_id", args.universe_id)

        log_event(logger, "NEWS_ALPHA_AGG", run_id=run_id, ticker_days=len(rec_rows))

        # Writes
        n_cache_written = 0
        n_recs_written = 0
        if not args.dry_run:
            n_cache_written = write_sentiment_cache(
                con,
                computed_cache_rows,
                overwrite=bool(args.overwrite),
                model=MODEL,
            )
            n_recs_written = write_recs(
                con,
                rec_rows,
                overwrite=bool(args.overwrite),
                date_from=date_from,
                date_to=date_to,
                firm=FIRM,
            )

        log_event(
            logger,
            "NEWS_ALPHA_DB_WRITE",
            run_id=run_id,
            sentiment_cache_rows=n_cache_written,
            recs_rows=n_recs_written,
            dry_run=bool(args.dry_run),
            overwrite=bool(args.overwrite),
        )

        if args.rejects_file:
            write_jsonl(args.rejects_file, rejects)
            log_event(
                logger,
                "NEWS_ALPHA_REJECTS_WRITTEN",
                run_id=run_id,
                rejects_rows=len(rejects),
                rejects_file=args.rejects_file,
            )

        log_event(
            logger,
            "NEWS_ALPHA_SUMMARY",
            run_id=run_id,
            fixtures_lines=len(raw_items),
            expanded=len(expanded),
            filtered=len(filtered),
            deduped=len(deduped),
            ticker_days=len(rec_rows),
            cache_written=n_cache_written,
            recs_written=n_recs_written,
            rejects_written=len(rejects) if args.rejects_file else 0,
        )

        log_event(logger, "NEWS_ALPHA_DONE", run_id=run_id)
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
