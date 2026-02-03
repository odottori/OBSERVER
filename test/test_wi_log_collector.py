# -*- coding: utf-8 -*-
"""
Collector-B unit tests.

We import wi_log_collector by running scripts/guardian.py collect (subprocess),
mirroring real usage (sys.path[0]==scripts/).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        env=dict(os.environ),
    )


def test_collect_normal_ok_with_empty_compileall(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    wi = "WI-7777"

    # compileall may legitimately be empty (EMPTY_OK), others must be non-empty.
    (reports / f"compileall_{wi}.log").write_text("", encoding="utf-8")
    for gate in (
        "guardian_lint",
        "import_smoke",
        "pytest",
        "guardian_sync",
        "guardian_derive",
        "build_master_md",
    ):
        (reports / f"{gate}_{wi}.log").write_text("ok\n", encoding="utf-8")

    p = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "collect",
            "--wi",
            wi,
            "--mode",
            "normal",
            "--reports-dir",
            str(reports),
        ]
    )
    assert p.returncode == 0, p.stdout


def test_collect_close_missing_fails(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    wi = "WI-6666"

    # Only one log exists; the others are missing -> non-zero
    (reports / f"guardian_lint_{wi}_CLOSE.log").write_text("ok\n", encoding="utf-8")

    p = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "collect",
            "--wi",
            wi,
            "--mode",
            "close",
            "--reports-dir",
            str(reports),
        ]
    )
    assert p.returncode != 0


def test_collect_hits_detected_and_optional_fail(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    wi = "WI-5555"

    for gate in (
        "guardian_lint",
        "guardian_sync",
        "guardian_derive",
        "build_master_md",
    ):
        (reports / f"{gate}_{wi}_CLOSE.log").write_text("OK\n", encoding="utf-8")

    # Add a failing marker in one log.
    (reports / f"guardian_sync_{wi}_CLOSE.log").write_text("ERROR: boom\n", encoding="utf-8")

    # Default behavior: HITS are reported but do not fail unless --fail-on-hits is set.
    p1 = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "collect",
            "--wi",
            wi,
            "--mode",
            "close",
            "--reports-dir",
            str(reports),
        ]
    )
    assert p1.returncode == 0, p1.stdout

    p2 = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "collect",
            "--wi",
            wi,
            "--mode",
            "close",
            "--reports-dir",
            str(reports),
            "--fail-on-hits",
        ]
    )
    assert p2.returncode != 0, p2.stdout
