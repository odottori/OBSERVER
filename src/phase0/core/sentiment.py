"""Local, deterministic sentiment scoring with DuckDB caching.

SENTINEL-ALPHA intentionally supports a *free* sentiment baseline:
- no paid/external sentiment API
- deterministic scoring (same text -> same score)
- caching in DuckDB (sentiment_cache)

This module is designed for auditability rather than maximum predictive power.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import duckdb

try:  # pragma: no cover
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
except Exception:  # pragma: no cover
    SentimentIntensityAnalyzer = None


# Minimal lexicon fallback (intentionally small, deterministic)
_POS = {
    "beat",
    "beats",
    "beating",
    "strong",
    "strength",
    "up",
    "upgrade",
    "upgraded",
    "outperform",
    "overweight",
    "buy",
    "bull",
    "bullish",
    "raise",
    "raised",
    "raises",
    "increase",
    "increased",
    "increases",
    "higher",
    "growth",
    "record",
    "surge",
    "surged",
    "positive",
    "improve",
    "improved",
    "improves",
}

_NEG = {
    "miss",
    "misses",
    "missing",
    "weak",
    "down",
    "downgrade",
    "downgraded",
    "underperform",
    "underweight",
    "sell",
    "bear",
    "bearish",
    "cut",
    "cuts",
    "cutting",
    "reduce",
    "reduced",
    "reduces",
    "lower",
    "decline",
    "declines",
    "declined",
    "negative",
    "risk",
    "lawsuit",
    "probe",
    "investigation",
}


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(frozen=True)
class SentimentResult:
    score: float
    model: str
    text_hash: str


class LocalSentimentScorer:
    """Score text in [-1, +1] with DuckDB caching."""

    def __init__(self, con: duckdb.DuckDBPyConnection | None = None, model: str = "auto"):
        self.con = con
        model = (model or "auto").strip().lower()

        self._vader = None
        if SentimentIntensityAnalyzer is not None and model in {"auto", "vader"}:
            try:
                self._vader = SentimentIntensityAnalyzer()
            except Exception:
                self._vader = None

        self.model = "vader" if self._vader is not None else "lexicon"

    def _score_lexicon(self, text: str) -> float:
        t = _normalize(text)
        if not t:
            return 0.0
        tokens = re.findall(r"[a-zA-Z]+", t)
        if not tokens:
            return 0.0
        pos = sum(1 for w in tokens if w in _POS)
        neg = sum(1 for w in tokens if w in _NEG)
        denom = max(1, pos + neg)
        score = (pos - neg) / denom
        # clamp
        if score > 1:
            score = 1.0
        if score < -1:
            score = -1.0
        return float(score)

    def _score(self, text: str) -> SentimentResult:
        t = _normalize(text)
        h = _hash_text(t)
        if self._vader is not None:
            try:
                s = float(self._vader.polarity_scores(text).get("compound", 0.0))
                # VADER already outputs [-1,1]
                return SentimentResult(score=max(-1.0, min(1.0, s)), model="vader", text_hash=h)
            except Exception:
                pass
        return SentimentResult(score=self._score_lexicon(text), model="lexicon", text_hash=h)

    def score(self, text: str) -> float:
        return float(self._score(text).score)

    def score_cached(self, text: str) -> float:
        """Score a text and cache it in DuckDB if possible."""

        res = self._score(text)
        if self.con is None:
            return float(res.score)

        try:
            row = self.con.execute(
                "SELECT score FROM sentiment_cache WHERE text_hash = ? LIMIT 1",
                [res.text_hash],
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        except Exception:
            # If the table is missing or unreadable, continue without caching.
            pass

        try:
            self.con.execute(
                """
                INSERT INTO sentiment_cache(text_hash, text, score, model, computed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(text_hash) DO NOTHING
                """,
                [res.text_hash, _normalize(text)[:2000], float(res.score), res.model, datetime.now(timezone.utc)],
            )
        except Exception:
            pass

        return float(res.score)
