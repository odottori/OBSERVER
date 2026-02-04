#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/doc_integrity_check.py

Doc integrity checker (offline).

Validates Markdown relative links inside the docset.

Checks
------
- Target file exists (for relative paths).
- Optional anchor exists (GitHub-style heading slug).

Ignores
-------
- External URLs (http/https/mailto/tel).
- Purely templated targets containing '{' or '}' to avoid false positives.

Modes
-----
- warn: never fails (returns 0) but prints findings.
- hard: fails (non-zero) if broken links/anchors are found.

This tool is intentionally conservative and scope-limited (docs/ and .doc/).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


# Match inline markdown links: [text](target)
# - Excludes images: ![alt](target)
_LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class Finding:
    kind: str  # FILE_MISSING | ANCHOR_MISSING
    src_file: Path
    src_line: int
    target: str
    resolved: Optional[Path]


def _is_external(target: str) -> bool:
    t = target.strip().lower()
    return (
        "://" in t
        or t.startswith("mailto:")
        or t.startswith("tel:")
        or t.startswith("data:")
    )


def _clean_target(raw: str) -> str:
    t = raw.strip()
    # Strip surrounding <...> syntax
    if t.startswith("<") and t.endswith(">"):
        t = t[1:-1].strip()

    # Drop optional title: (path "title") or (path 'title')
    if any(ch.isspace() for ch in t):
        t = t.split()[0]

    return t


def _slugify_heading(text: str) -> str:
    """GitHub-style slug for a Markdown heading."""
    s = text.strip().lower()
    # Remove punctuation except spaces/hyphens
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def _extract_anchors(md_text: str) -> Set[str]:
    anchors: Set[str] = set()
    counts: Dict[str, int] = {}

    for line in md_text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if not m:
            continue
        title = m.group(2).strip()
        if not title:
            continue

        base = _slugify_heading(title)
        if not base:
            continue

        # GitHub duplicates: foo, foo-1, foo-2, ...
        if base not in counts:
            counts[base] = 0
            anchors.add(base)
        else:
            counts[base] += 1
            anchors.add(f"{base}-{counts[base]}")

    # Also support explicit HTML anchors: <a id="...">
    for m in re.finditer(r"<a\s+[^>]*id=\"([^\"]+)\"", md_text, flags=re.IGNORECASE):
        anchors.add(m.group(1).strip())

    return anchors


def _resolve_target(
    *, repo_root: Path, src_file: Path, target: str
) -> Tuple[Optional[Path], Optional[str]]:
    """Return (resolved_path, anchor_or_none)."""
    t = _clean_target(target)
    if not t or "{" in t or "}" in t:
        return (None, None)

    anchor: Optional[str] = None
    path_part = t

    if "#" in t:
        path_part, anchor = t.split("#", 1)

    # Pure anchor refers to the same file.
    if path_part == "":
        return (src_file, anchor)

    # Root-relative links are interpreted as repo-root relative.
    if path_part.startswith("/"):
        resolved = (repo_root / path_part.lstrip("/")).resolve()
    else:
        resolved = (src_file.parent / path_part).resolve()

    return (resolved, anchor)


def _scan_file(*, repo_root: Path, md_path: Path) -> List[Finding]:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    anchors_cache: Dict[Path, Set[str]] = {}

    findings: List[Finding] = []

    # Precompute line offsets for link matches
    lines = text.splitlines()

    # Build a map from absolute character index to line number (1-based).
    # Lightweight: compute cumulative lengths.
    cum = [0]
    total = 0
    for ln in lines:
        total += len(ln) + 1
        cum.append(total)

    def idx_to_line(idx: int) -> int:
        # binary search in cum
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] <= idx:
                lo = mid + 1
            else:
                hi = mid
        return max(1, lo)

    for m in _LINK_RE.finditer(text):
        raw_target = m.group(1)
        target = _clean_target(raw_target)

        if not target or _is_external(target) or "{" in target or "}" in target:
            continue

        resolved, anchor = _resolve_target(repo_root=repo_root, src_file=md_path, target=target)
        src_line = idx_to_line(m.start())

        # If we couldn't resolve (e.g., templated), ignore.
        if resolved is None:
            continue

        if not resolved.exists():
            findings.append(
                Finding(
                    kind="FILE_MISSING",
                    src_file=md_path,
                    src_line=src_line,
                    target=target,
                    resolved=resolved,
                )
            )
            continue

        if anchor:
            if resolved not in anchors_cache:
                try:
                    tgt_text = resolved.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    tgt_text = ""
                anchors_cache[resolved] = _extract_anchors(tgt_text)

            anchors = anchors_cache[resolved]
            if anchor.strip() not in anchors:
                findings.append(
                    Finding(
                        kind="ANCHOR_MISSING",
                        src_file=md_path,
                        src_line=src_line,
                        target=target,
                        resolved=resolved,
                    )
                )

    return findings


def run_check(*, repo_root: Path, paths: Sequence[str]) -> List[Finding]:
    repo_root = repo_root.resolve()

    md_files: List[Path] = []
    for p in paths:
        base = (repo_root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
        if base.is_file() and base.suffix.lower() == ".md":
            md_files.append(base)
        elif base.is_dir():
            md_files.extend(sorted(base.rglob("*.md")))

    findings: List[Finding] = []
    for md in md_files:
        try:
            findings.extend(_scan_file(repo_root=repo_root, md_path=md))
        except Exception as e:
            # Treat parser errors as findings to keep behaviour observable.
            findings.append(
                Finding(
                    kind="EXCEPTION",
                    src_file=md,
                    src_line=1,
                    target=f"{type(e).__name__}: {e}",
                    resolved=None,
                )
            )

    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="guardian docs-check", description="Doc integrity check (offline).")
    ap.add_argument(
        "--mode",
        choices=["warn", "hard"],
        default="warn",
        help="warn: never fail; hard: fail on broken links/anchors",
    )
    ap.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: .)",
    )
    ap.add_argument(
        "--paths",
        action="append",
        default=None,
        help="Paths to scan (repeatable). Default: docs and .doc",
    )

    args = ap.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(args.repo_root)
    paths = args.paths if args.paths else ["docs", ".doc"]

    findings = run_check(repo_root=repo_root, paths=paths)

    if not findings:
        sys.stdout.write("DOCS-CHECK: OK (0 broken)\n")
        return 0

    # Print deterministic output (sorted)
    sys.stdout.write(f"DOCS-CHECK: BROKEN ({len(findings)})\n")
    for f in sorted(findings, key=lambda x: (str(x.src_file), x.src_line, x.kind, x.target)):
        rel = f.src_file
        try:
            rel = f.src_file.resolve().relative_to(repo_root.resolve())
        except Exception:
            pass

        if f.kind == "FILE_MISSING":
            sys.stdout.write(f"- FILE_MISSING {rel}:{f.src_line} -> {f.target}\n")
        elif f.kind == "ANCHOR_MISSING":
            sys.stdout.write(f"- ANCHOR_MISSING {rel}:{f.src_line} -> {f.target}\n")
        else:
            sys.stdout.write(f"- {f.kind} {rel}:{f.src_line} -> {f.target}\n")

    if args.mode == "hard":
        return 3

    # warn mode
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
