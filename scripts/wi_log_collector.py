#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/wi_log_collector.py

Collector "B" (Python): check expected WI logs in reports/.

Design goals
------------
- 1-command gate-friendly check.
- Robust against PowerShell UTF-16 (Out-File) logs.
- Output per log: OK / MISSING / EMPTY + HITS(n) with matching lines.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


DEFAULT_PATTERNS: Tuple[str, ...] = (
    # Backward-compatible default: hard-fail patterns.
    # Prefer using --profile hardfail|deprec|none.
    r"\bTRACEBACK\b",
    r"\[EXCEPTION\]",
    r"\bEXCEPTION\b",
    r"\bASSERTIONERROR\b",
    r"\bIMPORTERROR\b",
    r"\bMODULENOTFOUNDERROR\b",
    r"=+\s+(FAILURES|ERRORS)\s+=+",
    r"\bERROR\b",
    r"\bFAILED\b",
    r"\bFAIL\b",
)


PROFILE_PATTERNS: dict[str, Tuple[str, ...]] = {
    "hardfail": (
        r"\bTRACEBACK\b",
        r"\[EXCEPTION\]",
        r"\bEXCEPTION\b",
        r"\bASSERTIONERROR\b",
        r"\bIMPORTERROR\b",
        r"\bMODULENOTFOUNDERROR\b",
        r"=+\s+(FAILURES|ERRORS)\s+=+",
        r"\bERROR\b",
        r"\bFAILED\b",
        r"\bFAIL\b",
    ),
    "deprec": (
        r"DeprecationWarning",
        r"\[DEPRECATED\]",
    ),
    "none": (),
}

SKIP_HIT_PREFIXES: Tuple[str, ...] = (
    "CMD:",
    "DRY-RUN:",
)


NORMAL_GATES: Tuple[str, ...] = (
    "guardian_lint",
    "compileall",
    "import_smoke",
    "pytest",
    "guardian_sync",
    "guardian_derive",
    "build_master_md",
)

CLOSE_GATES: Tuple[str, ...] = (
    "guardian_lint",
    "guardian_sync",
    "guardian_derive",
    "build_master_md",
)


EMPTY_OK: Tuple[str, ...] = (
    "compileall",
)


@dataclass(frozen=True)
class LogHit:
    lineno: int
    line: str


@dataclass(frozen=True)
class LogCheck:
    gate: str
    path: Path
    status: str  # OK | MISSING | EMPTY
    hits: Tuple[LogHit, ...]


def _normalize_wi(raw: str) -> str:
    s = raw.strip().upper()
    if s.startswith("WI-"):
        digits = s[3:]
    else:
        digits = s

    digits = re.sub(r"\D", "", digits)
    if not digits:
        raise ValueError(f"Invalid WI '{raw}'. Expected WI-XXXX or XXXX.")

    return f"WI-{int(digits):04d}"


def _guess_decode(data: bytes) -> str:
    # PowerShell Out-File defaults to UTF-16 LE with BOM.
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except Exception:
            pass

    # Try UTF-8 first.
    try:
        text = data.decode("utf-8")
        # If this is really UTF-16 misread as UTF-8, NUL bytes leak as \x00.
        if "\x00" in text:
            raise UnicodeError("NULs detected")
        return text
    except Exception:
        pass

    # Fallbacks.
    for enc in ("utf-8-sig", "utf-16-le", "utf-16", "cp1252"):
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            continue

    return data.decode("utf-8", errors="replace")


def _read_text(path: Path) -> str:
    return _guess_decode(path.read_bytes())


def _iter_hits(text: str, rx: re.Pattern[str], max_hits: int) -> Tuple[LogHit, ...]:
    hits: List[LogHit] = []
    for i, line in enumerate(text.splitlines(), start=1):
        # Avoid false positives from runner metadata.
        if line.startswith(SKIP_HIT_PREFIXES):
            continue
        if rx.search(line):
            hits.append(LogHit(lineno=i, line=line.rstrip("\n")))
            if len(hits) >= max_hits:
                break
    return tuple(hits)


def _expected_files(wi: str, mode: str, reports_dir: Path) -> Tuple[Tuple[str, Path], ...]:
    mode = mode.lower().strip()
    if mode not in {"normal", "close"}:
        raise ValueError("mode must be 'normal' or 'close'")

    gates = NORMAL_GATES if mode == "normal" else CLOSE_GATES
    suffix = "" if mode == "normal" else "_CLOSE"

    out: List[Tuple[str, Path]] = []
    for gate in gates:
        out.append((gate, reports_dir / f"{gate}_{wi}{suffix}.log"))
    return tuple(out)


def collect(
    *,
    wi: str,
    mode: str,
    reports_dir: Path,
    patterns: Sequence[str],
    max_hits_per_file: int,
    fail_on_hits: bool,
) -> Tuple[int, Tuple[LogCheck, ...]]:
    rx: Optional[re.Pattern[str]]
    if patterns:
        rx = re.compile("|".join(f"(?:{p})" for p in patterns), flags=re.IGNORECASE)
    else:
        rx = None

    checks: List[LogCheck] = []
    missing = 0
    empty_bad = 0
    hits_total = 0

    for gate, path in _expected_files(wi, mode, reports_dir):
        if not path.exists():
            checks.append(LogCheck(gate=gate, path=path, status="MISSING", hits=()))
            missing += 1
            continue

        # Treat truly empty (0 bytes) as EMPTY, except allowlisted gates.
        if path.stat().st_size == 0:
            status = "OK" if gate in EMPTY_OK else "EMPTY"
            checks.append(LogCheck(gate=gate, path=path, status=status, hits=()))
            if status == "EMPTY":
                empty_bad += 1
            continue

        text = _read_text(path)
        if text.strip() == "":
            status = "OK" if gate in EMPTY_OK else "EMPTY"
            checks.append(LogCheck(gate=gate, path=path, status=status, hits=()))
            if status == "EMPTY":
                empty_bad += 1
            continue

        hits = _iter_hits(text, rx, max_hits_per_file) if rx is not None else ()
        hits_total += len(hits)
        checks.append(LogCheck(gate=gate, path=path, status="OK", hits=hits))

    rc = 0
    if missing or empty_bad:
        rc = 2
    elif fail_on_hits and hits_total:
        rc = 3

    return rc, tuple(checks)


def _format_checks(checks: Sequence[LogCheck]) -> str:
    lines: List[str] = []
    for c in checks:
        lines.append(f"{c.status:<7} {str(c.path)}  HITS({len(c.hits)})")
        for h in c.hits:
            lines.append(f"  L{h.lineno}: {h.line}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="guardian collect",
        description="Collector B: check expected WI logs in reports/",
    )
    p.add_argument("--wi", required=True, help="WI id, e.g. WI-0160 or 160")
    p.add_argument("--mode", choices=["normal", "close"], default="normal")
    p.add_argument("--reports-dir", default="reports", help="Reports directory (default: reports)")
    p.add_argument(
        "--profile",
        choices=["hardfail", "deprec", "none"],
        default="hardfail",
        help="Pattern profile (default: hardfail)",
    )
    p.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Extra regex pattern to count as HIT (repeatable)",
    )
    p.add_argument("--max-hits", type=int, default=25, help="Max hits per file (default: 25)")
    p.add_argument("--fail-on-hits", action="store_true", help="Non-zero exit if any HIT")
    p.add_argument(
        "--write-log",
        action="store_true",
        help="Also write collector output into reports/wi_collect_<WI>[_CLOSE].log",
    )

    args = p.parse_args(list(argv) if argv is not None else None)

    try:
        wi = _normalize_wi(args.wi)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    patterns_used: List[str] = list(PROFILE_PATTERNS.get(args.profile, ()))
    if args.pattern:
        patterns_used.extend(list(args.pattern))

    rc, checks = collect(
        wi=wi,
        mode=args.mode,
        reports_dir=reports_dir,
        patterns=patterns_used,
        max_hits_per_file=max(1, int(args.max_hits)),
        fail_on_hits=bool(args.fail_on_hits),
    )

    header = f"WI LOG COLLECTOR (B) — {wi} — mode={args.mode}\n"
    body = _format_checks(checks)
    sys.stdout.write(header)
    sys.stdout.write(body)

    if args.write_log:
        suffix = "" if args.mode == "normal" else "_CLOSE"
        out_path = reports_dir / f"wi_collect_{wi}{suffix}.log"
        out_path.write_text(header + body, encoding="utf-8")

        # Optional human-readable markdown snapshot.
        md_path = reports_dir / f"{date.today().isoformat()}_{wi}_collect{suffix}.md"
        md_path.write_text(
            "\n".join(
                [
                    f"# WI Log Collector (B) — {wi}",
                    "",
                    f"Mode: `{args.mode}`",
                    "",
                    f"Profile: `{args.profile}`",
                    "",
                    f"Fail on hits: `{bool(args.fail_on_hits)}`",
                    "",
                    "```",
                    header.strip(),
                    body.rstrip("\n"),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
