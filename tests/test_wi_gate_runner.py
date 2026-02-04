import subprocess
import sys
from pathlib import Path


def _run(cmd, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def test_gate_normal_writes_expected_logs_and_collects(tmp_path: Path):
    wi = "WI-0240"

    # Use dry-run so tests don't depend on DuckDB or external tooling.
    cp = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "gate",
            "--wi",
            wi,
            "--mode",
            "normal",
            "--reports-dir",
            str(tmp_path),
            "--dry-run",
            "--write-collect-log",
        ],
        cwd=Path.cwd(),
    )
    assert cp.returncode == 0, (cp.stdout, cp.stderr)

    # Gate logs (contract: 7)
    expected = [
        tmp_path / f"guardian_lint_{wi}.log",
        tmp_path / f"compileall_{wi}.log",
        tmp_path / f"import_smoke_{wi}.log",
        tmp_path / f"pytest_{wi}.log",
        tmp_path / f"guardian_sync_{wi}.log",
        tmp_path / f"guardian_derive_{wi}.log",
        tmp_path / f"build_master_md_{wi}.log",
    ]
    for lp in expected:
        assert lp.exists(), f"missing {lp.name}"
        assert lp.stat().st_size > 0, f"empty {lp.name}"

    # Extra (non-collector) logs
    assert (tmp_path / f"docs_check_{wi}.log").exists()
    assert (tmp_path / f"wi_gate_{wi}.log").exists()
    assert (tmp_path / f"wi_collect_{wi}.log").exists()


def test_gate_close_writes_expected_logs_and_collects(tmp_path: Path):
    wi = "WI-0240"

    cp = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "gate",
            "--wi",
            wi,
            "--mode",
            "close",
            "--reports-dir",
            str(tmp_path),
            "--dry-run",
            "--write-collect-log",
        ],
        cwd=Path.cwd(),
    )
    assert cp.returncode == 0, (cp.stdout, cp.stderr)

    # Gate logs (contract: 4)
    expected = [
        tmp_path / f"guardian_lint_{wi}_CLOSE.log",
        tmp_path / f"guardian_sync_{wi}_CLOSE.log",
        tmp_path / f"guardian_derive_{wi}_CLOSE.log",
        tmp_path / f"build_master_md_{wi}_CLOSE.log",
    ]
    for lp in expected:
        assert lp.exists(), f"missing {lp.name}"
        assert lp.stat().st_size > 0, f"empty {lp.name}"

    # Extra (non-collector) logs
    assert (tmp_path / f"docs_check_{wi}_CLOSE.log").exists()
    assert (tmp_path / f"wi_gate_{wi}_CLOSE.log").exists()
    assert (tmp_path / f"wi_collect_{wi}_CLOSE.log").exists()
