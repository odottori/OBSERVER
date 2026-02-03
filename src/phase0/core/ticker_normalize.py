"""Ticker normalization utilities.

Retail data sources often disagree on ticker punctuation (e.g. class shares as
"BRK.B" vs "BRK-B") and casing/whitespace. SENTINEL-ALPHA adopts a
conservative canonicalization policy:

- strip whitespace
- upper-case
- convert single-suffix dash notation ("XXXX-X") to dot notation ("XXXX.X")

The conversion is intentionally narrow: it only applies when the ticker matches
``^[A-Z0-9]+-[A-Z0-9]$`` (exactly one dash, one-character suffix).
"""

from __future__ import annotations

import re


_SINGLE_SUFFIX_DASH_RE = re.compile(r"^([A-Z0-9]+)-([A-Z0-9])$")


def normalize_ticker(ticker: str | None) -> str:
    """Return a canonical ticker string.

    The function is pure and deterministic.
    """
    if ticker is None:
        return ""
    t = str(ticker).strip().upper()
    if not t:
        return ""
    m = _SINGLE_SUFFIX_DASH_RE.match(t)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    return t


def normalize_ticker_sql(expr: str) -> str:
    """Return a DuckDB SQL expression that normalizes the ticker expression."""
    # DuckDB regex helpers: regexp_matches() returns boolean; regexp_replace() replaces.
    # We keep it intentionally narrow to avoid accidentally rewriting tickers with
    # multiple dashes.
    base = f"upper(trim({expr}))"
    return (
        f"CASE WHEN regexp_matches({base}, '^[A-Z0-9]+-[A-Z0-9]$') "
        f"THEN regexp_replace({base}, '-', '.') ELSE {base} END"
    )
