#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/wi_gate_runner.py

WI Gate Runner (Python) — one-command gate suite.

Design goals
------------
- PowerShell friendly: run as a single command (no PS functions).
- Deterministic log naming: `reports/<gate>_<WI>[ _CLOSE].log`.
- Normal mode: 7 logs (matches Collector B NORMAL_GATES).
- Close mode: 4 logs (matches Collector B CLOSE_GATES).
- Pytest uses strict DeprecationWarning gate by default.
- Always run Collector B at the end to verify log presence/emptiness.

Notes
-----
- This runner *creates* logs itself (no shell redirections required).
- In --dry-run mode, no external commands are executed; logs are stubbed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


# Keep log naming consistent with scripts/wi_log_collector.py
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


@dataclass(frozen=True)
class GateStep:
    gate: str
    argv: Tuple[str, ...]


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


def _log_path(*, reports_dir: Path, gate: str, wi: str, mode: str) -> Path:
    suffix = "" if mode == "normal" else "_CLOSE"
    return reports_dir / f"{gate}_{wi}{suffix}.log"


def _write_stub_log(path: Path, header: str, body_lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(body_lines).rstrip() + "\n", encoding="utf-8")


def _format_cmd_for_log(argv: Sequence[str]) -> str:
    """Format a command line for logs without triggering Collector B defaults.

    Collector B (wi_log_collector.py) flags generic markers like \bERROR\b.
    Pytest strict-deprecation uses the token `error::DeprecationWarning`, which
    would be a false-positive HIT if logged verbatim.

    We only sanitize *the logged representation*; the executed argv is unchanged.
    """

    out: List[str] = []
    for a in argv:
        # Avoid matching r"\bERROR\b" (case-insensitive) in collector defaults.
        # The substitution keeps the intent readable while removing the word-boundary.
        a = re.sub(r"(?i)\berror::", "error__", a)
        out.append(a)
    return " ".join(out)


def _append_footer(path: Path, lines: Sequence[str]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n" + "\n".join(lines).rstrip() + "\n")


def _run_subprocess(argv: Sequence[str], log_path: Path) -> int:
    # Ensure file is non-empty even if the command is quiet.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as f:
        try:
            p = subprocess.run(
                list(argv),
                stdout=f,
                stderr=subprocess.STDOUT,
                check=False,
                env=dict(os.environ),
            )
            return int(p.returncode)
        except Exception as e:
            f.write(f"\n[EXCEPTION] {type(e).__name__}: {e}\n")
            return 99




def _run_docs_check(*, wi: str, mode: str, reports_dir: Path, dry_run: bool, docs_check_mode: str, docs_paths: Sequence[str]) -> int:
    """Run docs-check and write a dedicated log in reports/.

    This log is intentionally *not* part of the Collector B expected set, so it
    does not alter the WI log count contract (7 normal, 4 close).
    """
    suffix = "" if mode == "normal" else "_CLOSE"
    lp = reports_dir / f"docs_check_{wi}{suffix}.log"

    py = sys.executable
    argv: List[str] = [py, "scripts/guardian.py", "docs-check", "--mode", docs_check_mode]
    for pth in docs_paths:
        argv += ["--paths", str(pth)]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"[{ts}] WI={wi} mode={mode} gate=docs_check"
    _write_stub_log(lp, header, [f"CMD: {_format_cmd_for_log(argv)}"])

    if dry_run:
        _append_footer(lp, ["DRY-RUN: command not executed.", "EXIT CODE: 0"])
        return 0

    rc = _run_subprocess(argv, lp)
    _append_footer(lp, [f"EXIT CODE: {rc}"])
    return int(rc)


def plan_steps(*, mode: str, strict_deprec: bool) -> Tuple[GateStep, ...]:
    py = sys.executable

    pytest_args = [py, "-m", "pytest", "-q"]
    if strict_deprec:
        pytest_args += ["-W", "error::DeprecationWarning"]

    normal: List[GateStep] = [
        GateStep("guardian_lint", (py, "scripts/guardian.py", "lint")),
        GateStep("compileall", (py, "-m", "compileall", "-q", "src")),
        GateStep("import_smoke", (py, "-c", "import src; print('OK')")),
        GateStep("pytest", tuple(pytest_args)),
        GateStep("guardian_sync", (py, "scripts/guardian.py", "sync", "--clean")),
        GateStep("guardian_derive", (py, "scripts/guardian.py", "derive")),
        GateStep("build_master_md", (py, "scripts/build_master_md.py")),
    ]

    close: List[GateStep] = [
        GateStep("guardian_lint", (py, "scripts/guardian.py", "lint")),
        GateStep("guardian_sync", (py, "scripts/guardian.py", "sync", "--clean")),
        GateStep("guardian_derive", (py, "scripts/guardian.py", "derive")),
        GateStep("build_master_md", (py, "scripts/build_master_md.py")),
    ]

    if mode == "normal":
        return tuple(normal)
    if mode == "close":
        return tuple(close)
    raise ValueError("mode must be 'normal' or 'close'")


def run_gate(
    *,
    wi: str,
    mode: str,
    reports_dir: Path,
    strict_deprec: bool,
    dry_run: bool,
    collect_profile: str,
    collect_fail_on_hits: bool,
    collect_patterns: Optional[List[str]],
    write_collect_log: bool,
    docs_check_mode: str,
    docs_paths: Optional[List[str]],
    docs_check_enabled: bool,
) -> int:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    steps = plan_steps(mode=mode, strict_deprec=strict_deprec)

    summary_lines: List[str] = []
    rc = 0
    for step in steps:
        lp = _log_path(reports_dir=reports_dir, gate=step.gate, wi=wi, mode=mode)
        header = f"[{ts}] WI={wi} mode={mode} gate={step.gate}"
        _write_stub_log(lp, header, [f"CMD: {_format_cmd_for_log(step.argv)}"])

        if dry_run:
            step_rc = 0
            _append_footer(lp, ["DRY-RUN: command not executed.", "EXIT CODE: 0"])
        else:
            step_rc = _run_subprocess(step.argv, lp)
            _append_footer(lp, [f"EXIT CODE: {step_rc}"])

        summary_lines.append(f"{step.gate}: {step_rc}")
        if step_rc != 0:
            rc = step_rc
            break



    # Docs integrity check (non-blocking in warn mode)
    if docs_check_enabled and rc == 0:
        _ = _run_docs_check(
            wi=wi,
            mode=mode,
            reports_dir=reports_dir,
            dry_run=dry_run,
            docs_check_mode=docs_check_mode,
            docs_paths=docs_paths if docs_paths else ["docs", ".doc"],
        )

    # Meta log (always non-empty)
    meta = reports_dir / f"wi_gate_{wi}{'' if mode=='normal' else '_CLOSE'}.log"
    _write_stub_log(
        meta,
        f"WI GATE RUNNER (B) — {wi} — mode={mode}",
        [
            f"started: {ts}",
            f"strict_deprec: {strict_deprec}",
            f"dry_run: {dry_run}",
            f"collect_profile: {collect_profile}",
            f"collect_fail_on_hits: {collect_fail_on_hits}",
            f"docs_check_enabled: {docs_check_enabled}",
            f"docs_check_mode: {docs_check_mode}",
            f"docs_paths: {docs_paths if docs_paths else ['docs', '.doc']}",
            "",
            "steps:",
            *[f"- {x}" for x in summary_lines],
            "",
            f"rc: {rc}",
        ],
    )

    # Collector B
    try:
        import wi_log_collector

        args: List[str] = ["--wi", wi, "--mode", mode, "--reports-dir", str(reports_dir)]
        args += ["--profile", collect_profile]
        if collect_fail_on_hits:
            args.append("--fail-on-hits")
        if write_collect_log:
            args.append("--write-log")
        if collect_patterns:
            for p in collect_patterns:
                args += ["--pattern", p]

        collector_rc = int(wi_log_collector.main(args))
    except Exception:
        collector_rc = 99

    # Prefer gate rc if gate failed; otherwise collector determines exit.
    return int(rc if rc != 0 else collector_rc)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="guardian gate",
        description="Run the WI gate suite and validate logs via Collector B.",
    )
    p.add_argument("--wi", required=True, help="WI id, e.g. WI-0240 or 240")
    p.add_argument("--mode", choices=["normal", "close"], default="normal")
    p.add_argument("--reports-dir", default="reports", help="Reports directory (default: reports)")
    p.add_argument(
        "--no-strict-deprec",
        action="store_true",
        help="Disable strict DeprecationWarning-as-error for pytest.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not execute commands; just write stub logs (for CI/unit tests).",
    )

    p.add_argument(
        "--collect-profile",
        choices=["hardfail", "deprec", "none"],
        default="hardfail",
        help="Collector profile (default: hardfail)",
    )
    p.add_argument(
        "--no-collect-fail-on-hits",
        action="store_true",
        help="Do not fail the overall gate if Collector B finds HITS",
    )

    p.add_argument(
        "--collect-pattern",
        action="append",
        default=None,
        help="Extra regex patterns for Collector B (repeatable).",
    )
    p.add_argument(
        "--write-collect-log",
        action="store_true",
        help="Also write Collector B output into reports/wi_collect_<WI>[_CLOSE].log",
    )


    p.add_argument(
        "--no-docs-check",
        action="store_true",
        help="Disable docs integrity check step.",
    )
    p.add_argument(
        "--docs-check-mode",
        choices=["warn", "hard"],
        default="warn",
        help="Docs integrity check mode (default: warn)",
    )
    p.add_argument(
        "--docs-path",
        action="append",
        default=None,
        help="Doc paths to scan (repeatable). Default: docs and .doc",
    )

    args = p.parse_args(list(argv) if argv is not None else None)

    try:
        wi = _normalize_wi(args.wi)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    reports_dir = Path(args.reports_dir)

    strict_deprec = not bool(args.no_strict_deprec)

    return int(
        run_gate(
            wi=wi,
            mode=args.mode,
            reports_dir=reports_dir,
            strict_deprec=strict_deprec,
            dry_run=bool(args.dry_run),
            collect_profile=str(args.collect_profile),
            collect_fail_on_hits=not bool(args.no_collect_fail_on_hits),
            collect_patterns=list(args.collect_pattern) if args.collect_pattern else None,
            write_collect_log=bool(args.write_collect_log),
            docs_check_mode=str(args.docs_check_mode),
            docs_paths=list(args.docs_path) if args.docs_path else None,
            docs_check_enabled=not bool(args.no_docs_check),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
