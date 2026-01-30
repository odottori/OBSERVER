from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


@dataclass(frozen=True)
class RawNewsItem:
    """A raw news record as loaded from fixtures."""

    line_no: int
    headline: str
    body: Optional[str]
    published_at: str
    source: str
    url: Optional[str]
    tickers: List[str]


def _get_body(obj: Dict[str, Any]) -> Optional[str]:
    for k in ("body", "summary", "description", "content", "text"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _get_tickers(obj: Dict[str, Any]) -> List[str]:
    # Common shapes
    if isinstance(obj.get("tickers"), list):
        return [str(x) for x in obj["tickers"] if str(x).strip()]
    if isinstance(obj.get("symbols"), list):
        return [str(x) for x in obj["symbols"] if str(x).strip()]

    if isinstance(obj.get("ticker"), str):
        return [obj["ticker"]]
    if isinstance(obj.get("symbol"), str):
        return [obj["symbol"]]

    return []


def load_fixtures_jsonl(path: str | Path) -> Iterator[RawNewsItem]:
    """Load fixtures from a JSONL file.

    Each line is a JSON object, recommended fields:
      - headline (str)
      - published_at (str; ISO8601)
      - source (str)
      - url (str; optional)
      - body/summary/description/content (optional)
      - ticker (str) or tickers (list[str])

    The loader is strict: malformed JSON or missing required fields raise.
    """

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    with p.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {i}: {e}") from e

            if not isinstance(obj, dict):
                raise ValueError(f"Line {i}: expected JSON object")

            # Backward-compatible field mapping: early collectors used `title`.
            headline = str(obj.get("headline") or obj.get("title") or "").strip()
            published_at = str(
                obj.get("published_at")
                or obj.get("published")
                or obj.get("pub_date")
                or obj.get("pubDate")
                or ""
            ).strip()

            if not headline:
                # Common operator error: passing a JSONL *log* (with `event` fields)
                # instead of fixtures rows.
                if "event" in obj and "ts" in obj:
                    raise ValueError(
                        f"Line {i}: expected a fixtures row but found an event/log record; pass a JSONL with news items"
                    )
                raise ValueError(f"Line {i}: missing required field 'headline'")
            if not published_at:
                raise ValueError(f"Line {i}: missing required field 'published_at'")

            source = str(obj.get("source") or "UNKNOWN").strip() or "UNKNOWN"
            url = obj.get("url")
            url = str(url).strip() if isinstance(url, str) and url.strip() else None

            tickers = _get_tickers(obj)

            yield RawNewsItem(
                line_no=i,
                headline=headline,
                body=_get_body(obj),
                published_at=published_at,
                source=source,
                url=url,
                tickers=tickers,
            )
