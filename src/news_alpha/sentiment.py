"""Deterministic sentiment scoring for NEWS-ALPHA (lexicon-v1).

This module is intentionally simple and fully offline:
- deterministic (same input text -> same output)
- no network and no external ML dependencies
- output score in [-1.0, +1.0]

Contract notes (per NEWS_ALPHA_SPEC.md v0.1):
- Normalization: trim, collapse whitespace, lowercase
- Tokenization: [A-Za-z]+ (keeps scoring locale-stable)
- Scoring: (pos - neg) / (pos + neg) if (pos+neg)>0 else 0.0
- text_hash: SHA-256 hex of normalized text
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


MODEL = "lexicon-v1"


# Keep the lexicon intentionally compact and deterministic.
# It is OK if the set is not exhaustive; the project values auditability.
#
# NOTE: We include a small bilingual (EN/IT) surface area because fixtures and
#       some EU sources may contain Italian headlines; the scoring contract is
#       still deterministic and offline.
_POS = {
    # EN
    "beat",
    "beats",
    "beating",
    "strong",
    "up",
    "upgrade",
    "upgraded",
    "upgrades",
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
    "gain",
    "gains",
    "rally",
    "rallies",
    "jump",
    "jumps",
    # IT
    "migliori",
    "migliore",
    "positivo",
    "positiva",
    "cresce",
    "crescita",
    "aumenta",
    "aumento",
    "rialzo",
    "supera",
}

_NEG = {
    # EN
    "miss",
    "misses",
    "missing",
    "weak",
    "down",
    "downgrade",
    "downgraded",
    "downgrades",
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
    # IT
    "peggiori",
    "peggiore",
    "negativo",
    "negativa",
    "calo",
    "scende",
    "rischio",
    "indagine",
    "causa",
}


def normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def text_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(frozen=True)
class SentimentResult:
    score: float
    model: str
    text_hash: str
    normalized_text: str


def score_text(headline: str, body: Optional[str] = None) -> SentimentResult:
    """Score headline + optional body.

    The pipeline calls this function for hashing/normalization as well as scoring.
    """

    combined = (headline or "").strip() if not body else f"{headline}\n{body}".strip()
    norm = normalize_text(combined)
    if not norm:
        return SentimentResult(score=0.0, model=MODEL, text_hash=text_hash(""), normalized_text="")

    tokens = re.findall(r"[A-Za-z]+", norm)
    if not tokens:
        return SentimentResult(score=0.0, model=MODEL, text_hash=text_hash(norm), normalized_text=norm)

    pos = sum(1 for w in tokens if w in _POS)
    neg = sum(1 for w in tokens if w in _NEG)

    denom = pos + neg
    score = 0.0 if denom == 0 else (pos - neg) / denom
    # Clamp defensively.
    if score > 1.0:
        score = 1.0
    if score < -1.0:
        score = -1.0

    return SentimentResult(score=float(score), model=MODEL, text_hash=text_hash(norm), normalized_text=norm)
