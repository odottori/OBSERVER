#!/usr/bin/env python3
"""Refresh docset + build MkDocs site in one command.

Pipeline
--------
1) Guardian direct mode:
   - sync --clean
   - lint
   - derive
2) Build master Markdown (PDF alternative):
   - scripts/build_master_md.py -> docs/OBSERVER_v1.2.5.md
3) MkDocs build:
   - mkdocs build -> _site/

Usage (PowerShell)
------------------
  py ./scripts/build_all_docs.py

Options
-------
  --skip-guardian
  --skip-master
  --skip-mkdocs
  --config mkdocs/mkdocs.yml
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def generate_mkdocs_views(rr: Path, env: dict) -> None:
    """Generate derived MkDocs pages (module cards) from canonical docs."""
    gen = rr / "scripts" / "gen_mkdocs_views.py"
    if gen.exists():
        import subprocess, sys
        cmd = [sys.executable, str(gen)]
        print("[mkdocs_views] $ " + " ".join(cmd))
        subprocess.run(cmd, cwd=str(rr), env=env, check=True)


def sync_docset_assets(rr: Path) -> None:
    """Sync non-canonical artifacts into mkdocs for local serving (allowed by contracts)."""
    src_pdf = rr / "docs" / "OBSERVER_v1.2.5.pdf"
    dst_pdf = rr / "mkdocs" / "docs" / "docset" / "OBSERVER_v1.2.5.pdf"
    dst_pdf.parent.mkdir(parents=True, exist_ok=True)
    if src_pdf.exists():
        try:
            import shutil
            shutil.copy2(src_pdf, dst_pdf)
        except Exception:
            pass



def run(cmd: list[str], *, cwd: Path, env: dict) -> None:
    print("[build_all_docs] $ " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def main(argv: list[str] | None = None) -> int:
    rr = repo_root()
    ap = argparse.ArgumentParser(prog="build_all_docs")
    ap.add_argument("--config", default=str(rr / "mkdocs" / "mkdocs.yml"))
    ap.add_argument("--skip-guardian", action="store_true")
    ap.add_argument("--skip-master", action="store_true")
    ap.add_argument("--skip-mkdocs", action="store_true")
    args = ap.parse_args(argv)

    env = dict(os.environ)
    rr_str = str(rr)

    # Ensure imports for mkdocstrings.
    py_path = env.get("PYTHONPATH", "").strip()
    parts = [p for p in py_path.split(os.pathsep) if p] if py_path else []
    if rr_str not in parts:
        parts.insert(0, rr_str)
    env["PYTHONPATH"] = os.pathsep.join(parts)

    try:
        if not args.skip_guardian:
            run([sys.executable, "scripts/guardian.py", "sync", "--clean"], cwd=rr, env=env)
            run([sys.executable, "scripts/guardian.py", "lint"], cwd=rr, env=env)
            run([sys.executable, "scripts/guardian.py", "derive"], cwd=rr, env=env)

        if not args.skip_master:
            master = rr / "scripts" / "build_master_md.py"
            if master.exists():
                run([sys.executable, str(master)], cwd=rr, env=env)

        if not args.skip_mkdocs:
            sync_docset_assets(rr)
            generate_mkdocs_views(rr, env)

            run([sys.executable, "-m", "mkdocs", "build", "--config-file", str(args.config)], cwd=rr, env=env)

        print("[build_all_docs] OK")
        return 0
    except subprocess.CalledProcessError as e:
        return int(e.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
