# -*- coding: utf-8 -*-
"""
Gate-runner smoke tests.

These tests are intentionally end-to-end (via subprocess) because guardian.py
relies on sys.path[0]==scripts/ for local module imports.
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


def test_gate_normal_writes_expected_logs_and_collects(tmp_path: Path) -> None:
    # Use a temp reports dir to avoid polluting the real reports/ during unit tests.
    reports = tmp_path / "reports"
    wi = "WI-9999"

    p = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "gate",
            "--wi",
            wi,
            "--mode",
            "normal",
            "--reports-dir",
            str(reports),
            "--dry-run",
            "--write-collect-log",
        ]
    )
    assert p.returncode == 0, p.stdout

    expected = [
        reports / f"{gate}_{wi}.log"
        for gate in (
            "guardian_lint",
            "compileall",
            "import_smoke",
            "pytest",
            "guardian_sync",
            "guardian_derive",
            "build_master_md",
        )
    ]
    for fp in expected:
        assert fp.exists(), f"missing {fp}"
        assert fp.stat().st_size > 0, f"empty {fp}"

    meta = reports / f"wi_gate_{wi}.log"
    assert meta.exists() and meta.stat().st_size > 0


def test_gate_close_writes_expected_logs_and_collects(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    wi = "WI-9998"

    p = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "gate",
            "--wi",
            wi,
            "--mode",
            "close",
            "--reports-dir",
            str(reports),
            "--dry-run",
            "--write-collect-log",
        ]
    )
    assert p.returncode == 0, p.stdout

    expected = [
        reports / f"{gate}_{wi}_CLOSE.log"
        for gate in (
            "guardian_lint",
            "guardian_sync",
            "guardian_derive",
            "build_master_md",
        )
    ]
    for fp in expected:
        assert fp.exists(), f"missing {fp}"
        assert fp.stat().st_size > 0, f"empty {fp}"

    meta = reports / f"wi_gate_{wi}_CLOSE.log"
    assert meta.exists() and meta.stat().st_size > 0
