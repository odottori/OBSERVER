from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_guardian_collect(*, reports_dir: Path, wi: str, mode: str = "normal", extra: list[str] | None = None):
    cmd = [
        sys.executable,
        "scripts/guardian.py",
        "collect",
        "--wi",
        wi,
        "--mode",
        mode,
        "--reports-dir",
        str(reports_dir),
        "--write-log",
    ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_collect_normal_ok_with_empty_compileall(tmp_path: Path):
    wi = "WI-0160"
    # Create expected logs.
    (tmp_path / f"guardian_lint_{wi}.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"compileall_{wi}.log").write_bytes(b"")  # allowed empty
    (tmp_path / f"import_smoke_{wi}.log").write_text("OK\n", encoding="utf-8")
    (tmp_path / f"pytest_{wi}.log").write_text("57 passed\n", encoding="utf-8")
    (tmp_path / f"guardian_sync_{wi}.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"guardian_derive_{wi}.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"build_master_md_{wi}.log").write_text("PASS\n", encoding="utf-8")

    r = _run_guardian_collect(reports_dir=tmp_path, wi=wi, mode="normal")
    assert r.returncode == 0
    assert "WI LOG COLLECTOR" in r.stdout
    assert "MISSING" not in r.stdout
    # compileall is allowlisted as "empty OK" and should show OK.
    assert f"compileall_{wi}.log" in r.stdout
    # Should not flag empty for allowlisted logs.
    assert "EMPTY" not in r.stdout

    # Ensure collector wrote its own log.
    assert (tmp_path / f"wi_collect_{wi}.log").exists()


def test_collect_close_missing_fails(tmp_path: Path):
    wi = "WI-0160"
    # Only create 3/4 close logs.
    (tmp_path / f"guardian_lint_{wi}_CLOSE.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"guardian_sync_{wi}_CLOSE.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"guardian_derive_{wi}_CLOSE.log").write_text("PASS\n", encoding="utf-8")

    r = _run_guardian_collect(reports_dir=tmp_path, wi=wi, mode="close")
    assert r.returncode != 0
    assert "MISSING" in r.stdout


def test_collect_hits_detected_and_optional_fail(tmp_path: Path):
    wi = "WI-0160"
    # Minimal close set.
    (tmp_path / f"guardian_lint_{wi}_CLOSE.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"guardian_sync_{wi}_CLOSE.log").write_text("PASS\n", encoding="utf-8")
    (tmp_path / f"guardian_derive_{wi}_CLOSE.log").write_text("Traceback: boom\n", encoding="utf-8")
    (tmp_path / f"build_master_md_{wi}_CLOSE.log").write_text("PASS\n", encoding="utf-8")

    r1 = _run_guardian_collect(reports_dir=tmp_path, wi=wi, mode="close")
    assert r1.returncode == 0
    assert "HITS(1)" in r1.stdout
    assert "Traceback" in r1.stdout

    r2 = _run_guardian_collect(reports_dir=tmp_path, wi=wi, mode="close", extra=["--fail-on-hits"])
    assert r2.returncode != 0