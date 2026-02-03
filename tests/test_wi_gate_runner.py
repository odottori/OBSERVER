from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_guardian_gate(*, reports_dir: Path, wi: str, mode: str = "normal"):
    cmd = [
        sys.executable,
        "scripts/guardian.py",
        "gate",
        "--wi",
        wi,
        "--mode",
        mode,
        "--reports-dir",
        str(reports_dir),
        "--dry-run",
        "--write-collect-log",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_gate_normal_writes_expected_logs_and_collects(tmp_path: Path):
    wi = "WI-0240"
    r = _run_guardian_gate(reports_dir=tmp_path, wi=wi, mode="normal")
    assert r.returncode == 0
    assert "WI LOG COLLECTOR" in r.stdout

    # Expected normal logs
    for gate in [
        "guardian_lint",
        "compileall",
        "import_smoke",
        "pytest",
        "guardian_sync",
        "guardian_derive",
        "build_master_md",
    ]:
        p = tmp_path / f"{gate}_{wi}.log"
        assert p.exists()
        assert p.stat().st_size > 0

    # Meta log + collector log
    assert (tmp_path / f"wi_gate_{wi}.log").exists()
    assert (tmp_path / f"wi_collect_{wi}.log").exists()

    # Strict deprec should be enabled by default.
    # The runner sanitizes the *logged* command to avoid Collector B false positives
    # on the token "error::DeprecationWarning" (matches r"\bERROR\b").
    pytest_log = (tmp_path / f"pytest_{wi}.log").read_text(encoding="utf-8")
    assert "-W" in pytest_log
    assert "error__DeprecationWarning" in pytest_log
    assert "error::DeprecationWarning" not in pytest_log

    # Meta log should explicitly record strict_deprec mode.
    meta = (tmp_path / f"wi_gate_{wi}.log").read_text(encoding="utf-8")
    assert "strict_deprec: True" in meta


def test_gate_close_writes_expected_logs_and_collects(tmp_path: Path):
    wi = "WI-0240"
    r = _run_guardian_gate(reports_dir=tmp_path, wi=wi, mode="close")
    assert r.returncode == 0

    for gate in ["guardian_lint", "guardian_sync", "guardian_derive", "build_master_md"]:
        p = tmp_path / f"{gate}_{wi}_CLOSE.log"
        assert p.exists()
        assert p.stat().st_size > 0

    assert (tmp_path / f"wi_gate_{wi}_CLOSE.log").exists()
    assert (tmp_path / f"wi_collect_{wi}_CLOSE.log").exists()
