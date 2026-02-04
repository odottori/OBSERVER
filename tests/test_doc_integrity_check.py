import subprocess
import sys
from pathlib import Path


def _run(cmd, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def test_docs_check_warn_does_not_fail_but_reports(tmp_path: Path):
    # Build an isolated docset
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)

    (docs / "b.md").write_text(
        "# B\n\n## Target\n\nOk\n",
        encoding="utf-8",
    )
    (docs / "a.md").write_text(
        "# A\n\n- [ok](b.md)\n- [ok anchor](b.md#target)\n- [missing](missing.md)\n",
        encoding="utf-8",
    )

    cp = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "docs-check",
            "--mode",
            "warn",
            "--repo-root",
            str(tmp_path),
            "--paths",
            "docs",
        ],
        cwd=Path.cwd(),
    )
    assert cp.returncode == 0
    assert "BROKEN" in cp.stdout
    assert "FILE_MISSING" in cp.stdout


def test_docs_check_hard_fails_on_broken(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)

    (docs / "x.md").write_text(
        "# X\n\n- [missing](missing.md)\n- [anchor-miss](x.md#nope)\n",
        encoding="utf-8",
    )

    cp = _run(
        [
            sys.executable,
            "scripts/guardian.py",
            "docs-check",
            "--mode",
            "hard",
            "--repo-root",
            str(tmp_path),
            "--paths",
            "docs",
        ],
        cwd=Path.cwd(),
    )
    assert cp.returncode != 0
    assert "FILE_MISSING" in cp.stdout or "ANCHOR_MISSING" in cp.stdout
