"""Ticker mapping integrity gate.

Purpose
-------
Retail data providers (yfinance/stooq) frequently introduce symbol drift:
re-tickerings after mergers, punctuation differences (e.g., BRK.B vs BRK-B),
and multiple aliases over time.

`ticker_mappings` is the canonical mechanism to control this drift in a
time-bounded, audit-friendly manner.

This gate fails fast if the mapping table is internally inconsistent:
- overlapping validity windows for the same alias
- invalid date ranges (end_date < start_date)
- *effective* cycles (a mapping chain that can return to the same ticker
  for some non-empty time intersection)

Warnings (non-fatal by default):
- non-canonical class-share notation (dash vs dot)
- unusually long alias chains (often indicates drift that should be
  consolidated)

Usage
-----
<PY> -m src.tools.verify_ticker_mappings --db data/sentinel_alpha.db

Exit codes
----------
0 PASS
1 FAIL (gate violated)
2 ERROR (unexpected failure)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date

import duckdb

from src.phase0.db.migrate import ensure_schema


_TRUTHY = {"1", "true", "yes", "y", "on"}


def _as_date(d) -> date | None:
    if d is None:
        return None
    if isinstance(d, date):
        return d
    # DuckDB can return strings in some contexts.
    try:
        return date.fromisoformat(str(d)[:10])
    except Exception:
        return None


def normalize_ticker(raw: str | None) -> str:
    """Project-wide conservative ticker normalizer.

    - trims and uppercases
    - converts common class-share dash notation to dot (e.g., BRK-B -> BRK.B)
      only when the suffix is a single alphanumeric character
    """
    t = (raw or "").strip().upper()
    if not t:
        return ""
    # Only normalize the simplest and most common class-share forms.
    # Keep it conservative to avoid accidental rewrites of other exchanges.
    if re.fullmatch(r"[A-Z0-9]{1,12}-[A-Z0-9]", t):
        return t.replace("-", ".")
    return t


def _interval_end(d: date | None) -> date:
    # Treat open-ended as far future.
    return d if d is not None else date(9999, 12, 31)


def _intersect(a0: date, a1: date, b0: date, b1: date) -> tuple[date, date] | None:
    s = max(a0, b0)
    e = min(a1, b1)
    if s <= e:
        return (s, e)
    return None


@dataclass(frozen=True)
class MappingRow:
    alias_raw: str
    canonical_raw: str
    alias: str
    canonical: str
    start: date | None
    end: date | None
    source: str | None
    notes: str | None

    @property
    def end_effective(self) -> date:
        return _interval_end(self.end)


def load_mappings(con: duckdb.DuckDBPyConnection) -> list[MappingRow]:
    rows = con.execute(
        """
        SELECT alias_ticker, canonical_ticker, start_date, end_date, source, notes
        FROM ticker_mappings
        ORDER BY alias_ticker, start_date
        """
    ).fetchall()
    out: list[MappingRow] = []
    for r in rows:
        alias_raw = (r[0] or "").strip()
        canonical_raw = (r[1] or "").strip()
        alias = normalize_ticker(alias_raw)
        canonical = normalize_ticker(canonical_raw)
        start = _as_date(r[2])
        end = _as_date(r[3])
        out.append(
            MappingRow(
                alias_raw=alias_raw,
                canonical_raw=canonical_raw,
                alias=alias,
                canonical=canonical,
                start=start,
                end=end,
                source=r[4],
                notes=r[5],
            )
        )
    return out


def check_ticker_mappings(
    con: duckdb.DuckDBPyConnection,
    sample_limit: int = 20,
    max_chain_len_warn: int = 4,
    enable_warnings: bool = True,
) -> dict:
    """Return a dict with problems/warnings and summary counts."""

    sample_limit = max(0, int(sample_limit))
    max_chain_len_warn = max(1, int(max_chain_len_warn))

    mappings = load_mappings(con)

    failures: list[str] = []
    warnings: list[str] = []

    # Basic row validity.
    invalid_rows: list[str] = []
    for m in mappings:
        if not m.alias or not m.canonical or m.start is None:
            invalid_rows.append(f"{m.alias!r}->{m.canonical!r} start={m.start}")
            continue
        if m.end is not None and m.end < m.start:
            invalid_rows.append(f"{m.alias}->{m.canonical} [{m.start}..{m.end}]")

        # Non-fatal normalization warnings (dash vs dot).
        if enable_warnings:
            a0 = (m.alias_raw or "").strip().upper()
            c0 = (m.canonical_raw or "").strip().upper()
            # Warn if the stored values are not already canonical under our
            # conservative normalization (most notably class-share dash forms).
            if normalize_ticker(a0) != a0 or normalize_ticker(c0) != c0:
                warnings.append(f"non-canonical ticker notation: {a0}->{c0} (canonical: {m.alias}->{m.canonical})")

    if invalid_rows:
        failures.append(f"invalid mapping rows: {len(invalid_rows)}")

    # Overlap detection per alias.
    overlaps: list[str] = []
    by_alias: dict[str, list[MappingRow]] = {}
    for m in mappings:
        if m.alias and m.start is not None:
            by_alias.setdefault(m.alias, []).append(m)

    for alias, items in by_alias.items():
        items_sorted = sorted(items, key=lambda x: x.start)
        prev: MappingRow | None = None
        for cur in items_sorted:
            if prev is None:
                prev = cur
                continue
            # Intervals are inclusive; require strict separation.
            if prev.end is None or prev.end_effective >= cur.start:
                overlaps.append(
                    f"{alias}: [{prev.start}..{prev.end}] overlaps [{cur.start}..{cur.end}]"
                )
            # Advance only if current ends later, to catch chains.
            if cur.end_effective > prev.end_effective:
                prev = cur

    if overlaps:
        failures.append(f"overlapping mapping windows: {len(overlaps)}")

    # Cycle detection with interval intersection.
    # Build adjacency: alias -> list[MappingRow] (edge alias->canonical with interval)
    #
    # IMPORTANT: identity mappings (alias == canonical) are explicitly allowed by
    # contract (they are effectively "no-op" declarations). They must NOT be
    # treated as cycles, otherwise any identity row would trip the gate.
    #
    # We therefore exclude identity edges from the cycle graph.
    adj: dict[str, list[MappingRow]] = {
        k: [e for e in v if e.alias and e.canonical and e.alias != e.canonical]
        for k, v in by_alias.items()
    }

    cycles: list[str] = []

    def dfs(
        start_alias: str,
        cur_ticker: str,
        path: list[str],
        interval: tuple[date, date],
        depth: int,
        max_depth: int = 10,
    ) -> None:
        if depth >= max_depth:
            return
        edges = adj.get(cur_ticker, [])
        for e in edges:
            if e.start is None:
                continue
            inter = _intersect(interval[0], interval[1], e.start, e.end_effective)
            if inter is None:
                continue
            nxt = e.canonical
            if not nxt:
                continue
            if nxt == start_alias:
                cycles.append(f"{'->'.join(path + [nxt])} @ [{inter[0]}..{inter[1]}]")
                continue
            if nxt in path:
                # A cycle that does not necessarily return to start_alias, but still
                # indicates ambiguous canonicalization.
                idx = path.index(nxt)
                cyc = path[idx:] + [nxt]
                cycles.append(f"{'->'.join(cyc)} @ [{inter[0]}..{inter[1]}]")
                continue
            dfs(start_alias, nxt, path + [nxt], inter, depth + 1, max_depth=max_depth)

    for m in mappings:
        if not m.alias or not m.canonical or m.start is None:
            continue
        # Identity rows are allowed, but they must not trigger the cycle gate.
        if m.alias == m.canonical:
            continue
        # Start the DFS with this edge interval.
        dfs(m.alias, m.canonical, [m.alias, m.canonical], (m.start, m.end_effective), depth=0)

    # Deduplicate cycle strings (may appear multiple times).
    cycles = sorted(set(cycles))
    if cycles:
        failures.append(f"effective mapping cycles: {len(cycles)}")

    # Chain length heuristic (warn-only).
    # For each alias, follow canonical pointers ignoring dates (conservative upper bound).
    if enable_warnings:
        chain_warns: list[str] = []
        for alias in by_alias.keys():
            # Pick the latest mapping row by start_date as "current".
            rows = sorted(by_alias[alias], key=lambda x: x.start)
            cur = rows[-1]
            seen: set[str] = set()
            chain: list[str] = [alias]
            nxt = cur.canonical
            while nxt and nxt not in seen and len(chain) <= 20:
                seen.add(nxt)
                chain.append(nxt)
                if nxt not in by_alias:
                    break
                nxt = sorted(by_alias[nxt], key=lambda x: x.start)[-1].canonical

            if len(chain) > max_chain_len_warn:
                chain_warns.append(f"long alias chain (len={len(chain)}): {'->'.join(chain)}")
        warnings.extend(sorted(set(chain_warns)))

    # Prepare structured output.
    out = {
        "n_rows": len(mappings),
        "n_aliases": len(by_alias),
        "invalid_rows": invalid_rows[:sample_limit],
        "overlap_samples": overlaps[:sample_limit],
        "cycle_samples": cycles[:sample_limit],
        "warnings": warnings[:sample_limit],
        "n_invalid": len(invalid_rows),
        "n_overlaps": len(overlaps),
        "n_cycles": len(cycles),
        "n_warnings": len(warnings),
        "failures": failures,
    }
    return out


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="verify_ticker_mappings", description="Ticker mapping integrity gate")
    p.add_argument("--db", "--db-path", dest="db_path", default="data/sentinel_alpha.db", help="Path to DuckDB db")
    p.add_argument("--sample-limit", type=int, default=20, help="Sample size for diagnostics")
    p.add_argument(
        "--max-chain-len-warn",
        type=int,
        default=4,
        help="Warn when a (latest) alias chain exceeds this length (default: 4)",
    )
    p.add_argument(
        "--no-warnings",
        action="store_true",
        help="Disable warnings output (still fails on hard integrity issues)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])
    try:
        con = duckdb.connect(database=args.db_path)
        ensure_schema(con)
        rep = check_ticker_mappings(
            con,
            sample_limit=args.sample_limit,
            max_chain_len_warn=args.max_chain_len_warn,
            enable_warnings=not bool(args.no_warnings),
        )

        if rep.get("failures"):
            print("[FAIL] verify_ticker_mappings")
            for f in rep["failures"]:
                print(f"  - {f}")
            for k, title in (
                ("invalid_rows", "invalid rows"),
                ("overlap_samples", "overlap samples"),
                ("cycle_samples", "cycle samples"),
            ):
                items = rep.get(k) or []
                if items:
                    print(f"  - {title}:")
                    for it in items[: args.sample_limit]:
                        print(f"      {it}")
            raise SystemExit(1)

        print("[PASS] verify_ticker_mappings")
        print(
            f"  rows={rep.get('n_rows')}; aliases={rep.get('n_aliases')}; "
            f"overlaps={rep.get('n_overlaps')}; cycles={rep.get('n_cycles')}; invalid={rep.get('n_invalid')}"
        )
        if not args.no_warnings and (rep.get("warnings") or []):
            print(f"  warnings={rep.get('n_warnings')}")
            for w in (rep.get("warnings") or [])[: args.sample_limit]:
                print(f"    - {w}")
        raise SystemExit(0)

    except SystemExit:
        raise
    except Exception as e:
        print("[ERROR] verify_ticker_mappings:", str(e))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
