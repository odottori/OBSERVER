import re
from pathlib import Path

LEGACY_RX = re.compile(r"^\s*(from|import)\s+src\.core\b")


def _scan_dir(root: Path) -> list[str]:
    offenders: list[str] = []
    for p in root.rglob("*.py"):
        # allow the shim package itself to exist (but forbid other code using it)
        if "src/core" in p.as_posix().replace("\\\\", "/"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if LEGACY_RX.search(line):
                offenders.append(f"{p.as_posix()}:{i}: {line.strip()}")
    return offenders


def test_no_legacy_imports_from_src_core():
    repo_root = Path(__file__).resolve().parents[1]
    targets = [repo_root / "src", repo_root / "scripts", repo_root / "test", repo_root / "tests"]

    offenders: list[str] = []
    for t in targets:
        if t.exists():
            offenders.extend(_scan_dir(t))

    assert offenders == [], "Legacy imports from src.core remain:\n" + "\n".join(offenders)
