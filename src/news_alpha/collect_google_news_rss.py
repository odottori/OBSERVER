"""Google News RSS collector for NEWS-ALPHA.

This tool is intentionally *not* part of the audited trading pipeline.
Its purpose is to generate offline fixtures (JSONL) that can be consumed by
`<PY> -m src.news_alpha.run`.

Modes:
- Online fetch (guarded): download RSS XML from Google News.
- Offline parse: parse already-downloaded XML files from a raw directory.

The default operational posture is offline. Online fetch requires explicit opt-in
via NEWS_ALPHA_ALLOW_ONLINE=1.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .db import connect_db, fetch_universe_tickers, table_exists
from .run import normalize_ticker, parse_yyyymmdd


@dataclass
class Stats:
    items_raw: int = 0
    items_kept: int = 0
    items_rej_domain: int = 0
    items_rej_date: int = 0
    # Data-quality / observability counters.
    tickers_requested: int = 0
    tickers_with_raw: int = 0
    raw_files_missing: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "items_raw": int(self.items_raw),
            "items_kept": int(self.items_kept),
            "items_rej_domain": int(self.items_rej_domain),
            "items_rej_date": int(self.items_rej_date),
            "tickers_requested": int(self.tickers_requested),
            "tickers_with_raw": int(self.tickers_with_raw),
            "raw_files_missing": int(self.raw_files_missing),
        }


def _offline_guard(online_requested: bool) -> None:
    if not online_requested:
        return
    if os.getenv("NEWS_ALPHA_ALLOW_ONLINE", "0") == "1":
        return
    raise SystemExit("Online mode is disabled unless NEWS_ALPHA_ALLOW_ONLINE=1")


def _strip_html(s: str) -> str:
    # Remove HTML tags (very small, deterministic cleaner).
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _canonical_xml_name(ticker: str, when_days: int) -> str:
    return f"google_news_{ticker}_when{int(when_days)}d.xml"


def _legacy_xml_name(ticker: str) -> str:
    # Historical naming observed in early repo snapshots.
    return f"google_news_{ticker}.xml"


def _candidate_xml_paths(raw_dir: Path, ticker: str, when_days: int) -> List[Path]:
    """Return candidate XML paths for a given ticker.

    We support both canonical and legacy naming, and optionally a "google_news"
    subdirectory (older layouts wrote into raw_dir/google_news/).
    """

    canon = _canonical_xml_name(ticker, when_days)
    legacy = _legacy_xml_name(ticker)
    candidates = [
        raw_dir / canon,
        raw_dir / legacy,
        raw_dir / "google_news" / canon,
        raw_dir / "google_news" / legacy,
    ]
    # De-duplicate while preserving order.
    seen = set()
    out: List[Path] = []
    for p in candidates:
        ps = str(p)
        if ps in seen:
            continue
        seen.add(ps)
        out.append(p)
    return out


def _build_google_news_url(ticker: str, when_days: int) -> str:
    # Use a conservative query; the collector is for fixtures only.
    q = f"{ticker} analyst upgrade OR downgrade OR rating"
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(q)
        + f"%20when:{int(when_days)}d&hl=en-US&gl=US&ceid=US:en"
    )


def _fetch_rss_xml(url: str) -> str:
    # Keep headers minimal; deterministic behaviour is not required here.
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="ignore")


def _iter_items_from_xml(xml_text: str) -> Iterable[ElementTree.Element]:
    root = ElementTree.fromstring(xml_text)
    for item in root.findall(".//item"):
        yield item


def _source_domain_allowed(source_url: str, allowed_domains: List[str]) -> bool:
    if not allowed_domains:
        return True
    u = (source_url or "").lower()
    # Allow either exact match in hostname or substring match in URL.
    # The RSS fixture uses fully qualified URLs (https://www.ilsole24ore.com).
    return any(d.lower() in u for d in allowed_domains)


def _parse_pubdate(pub_date_raw: str) -> datetime:
    """Parse RSS pubDate (RFC 822-ish) into a UTC datetime."""

    # Typical format: "Mon, 13 Jan 2026 10:00:00 GMT"
    dt = parsedate_to_datetime(pub_date_raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_item(
    item: ElementTree.Element,
    *,
    ticker: str,
    date_from: datetime.date,
    date_to: datetime.date,
    allowed_domains: List[str],
    stats: Stats,
) -> Optional[Dict[str, Any]]:
    stats.items_raw += 1

    title = _strip_html((item.findtext("title") or "").strip())
    link = (item.findtext("link") or "").strip() or None
    pub_date_raw = (item.findtext("pubDate") or "").strip()
    try:
        published_dt = _parse_pubdate(pub_date_raw)
    except Exception:
        # If the input is malformed, treat it as out-of-range.
        stats.items_rej_date += 1
        return None
    published_d = published_dt.date()

    src_el = item.find("source")
    source = _strip_html((src_el.text or "").strip()) if src_el is not None else ""
    source_url = (src_el.attrib.get("url") if src_el is not None else "") or ""

    if not _source_domain_allowed(source_url, allowed_domains):
        stats.items_rej_domain += 1
        return None
    if published_d < date_from or published_d > date_to:
        stats.items_rej_date += 1
        return None

    # Description/body is optional; keep it deterministic and small.
    desc = item.findtext("description") or ""
    body = _strip_html(desc)
    if not body:
        body = None

    stats.items_kept += 1
    return {
        "published_at": published_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": source,
        "url": link,
        "headline": title,
        "body": body,
        "tickers": [ticker],
        "source_url": source_url,
    }


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="news-alpha-collector")
    p.add_argument("--db", required=True, help="Path to DuckDB database")
    p.add_argument("--universe-id", default="ALL", help="Universe id to scan")
    p.add_argument("--date-from", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--date-to", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--when-days", type=int, default=14, help="Google News query window in days")
    p.add_argument("--domains", action="append", default=[], help="Allowed source domains (repeatable)")
    p.add_argument("--raw-dir", default=os.path.join("REPORTS", "news_alpha", "raw", "rss"), help="Directory for raw XML")
    p.add_argument("--out-fixtures", help="Output JSONL fixtures path")
    p.add_argument("--stats-file", help="Output stats JSON path")
    p.add_argument("--offline-parse", action="store_true", help="Parse existing raw XML files")
    p.add_argument("--online", action="store_true", help="Fetch RSS from the network (guarded)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)

    date_from = parse_yyyymmdd(args.date_from)
    date_to = parse_yyyymmdd(args.date_to)
    if date_to < date_from:
        raise SystemExit("--date-to must be >= --date-from")

    # Online fetch is optional and guarded.
    _offline_guard(bool(args.online))

    raw_dir = Path(args.raw_dir)
    out_fixtures = Path(args.out_fixtures) if args.out_fixtures else None
    stats_file = Path(args.stats_file) if args.stats_file else None

    con = connect_db(args.db)
    try:
        if not table_exists(con, "universe_membership"):
            raise SystemExit("Missing required table: universe_membership")
        tickers_raw = fetch_universe_tickers(con, args.universe_id, date_from, date_to)
    finally:
        con.close()

    tickers = [t for t in (normalize_ticker(x) for x in tickers_raw) if t]
    if not tickers:
        # No universe tickers; nothing to do.
        if stats_file:
            _write_json(stats_file, Stats().as_dict())
        return 0

    rows: List[Dict[str, Any]] = []
    st = Stats(tickers_requested=len(tickers))

    for t in tickers:
        canon_name = _canonical_xml_name(t, int(args.when_days))
        canon_path = raw_dir / canon_name

        xml_text: Optional[str] = None
        if args.offline_parse:
            # Offline parse: accept multiple historical file layouts.
            chosen: Optional[Path] = None
            for cand in _candidate_xml_paths(raw_dir, t, int(args.when_days)):
                if cand.exists():
                    chosen = cand
                    break
            if chosen is None:
                st.raw_files_missing += 1
                continue
            st.tickers_with_raw += 1
            xml_text = chosen.read_text(encoding="utf-8", errors="ignore")
        elif args.online:
            # Fetch and persist for reproducibility.
            raw_dir.mkdir(parents=True, exist_ok=True)
            xml_text = _fetch_rss_xml(_build_google_news_url(t, int(args.when_days)))
            canon_path.write_text(xml_text, encoding="utf-8")
        else:
            # No mode selected: default to offline parse if any candidate file exists.
            chosen: Optional[Path] = None
            for cand in _candidate_xml_paths(raw_dir, t, int(args.when_days)):
                if cand.exists():
                    chosen = cand
                    break
            if chosen is None:
                st.raw_files_missing += 1
                continue
            st.tickers_with_raw += 1
            xml_text = chosen.read_text(encoding="utf-8", errors="ignore")

        for item in _iter_items_from_xml(xml_text or ""):
            row = _parse_item(
                item,
                ticker=t,
                date_from=date_from,
                date_to=date_to,
                allowed_domains=list(args.domains or []),
                stats=st,
            )
            if row is not None:
                rows.append(row)

    # Deterministic output order.
    rows.sort(key=lambda r: (r.get("published_at") or "", r.get("url") or "", r.get("headline") or ""))

    if out_fixtures:
        _write_jsonl(out_fixtures, rows)
    if stats_file:
        _write_json(stats_file, st.as_dict())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
