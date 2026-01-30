#!/usr/bin/env python3
"""Serve MkDocs (code docs) with a deterministic environment.

Why this exists
---------------
mkdocstrings imports Python modules (e.g. `src.*`). On Windows, that typically
requires the repository root to be on `PYTHONPATH`. This script enforces that
and runs MkDocs with the project config.

Usage (PowerShell)
------------------
  py ./scripts/serve_code_docs.py

Options
-------
  --config mkdocs/mkdocs.yml
  --host 127.0.0.1
  --port 8000
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



def main(argv: list[str] | None = None) -> int:
    rr = repo_root()
    ap = argparse.ArgumentParser(prog="serve_code_docs")
    ap.add_argument("--config", default=str(rr / "mkdocs" / "mkdocs.yml"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    env = dict(os.environ)
    rr_str = str(rr)

    # Ensure repo root is on PYTHONPATH (needed for mkdocstrings imports).
    py_path = env.get("PYTHONPATH", "").strip()
    parts = [p for p in py_path.split(os.pathsep) if p] if py_path else []
    if rr_str not in parts:
        parts.insert(0, rr_str)
    env["PYTHONPATH"] = os.pathsep.join(parts)

    sync_docset_assets(rr)
    generate_mkdocs_views(rr, env)

    cmd = [
        sys.executable, "-m", "mkdocs",
        "serve",
        "--config-file", str(args.config),
        "--dev-addr", f"{args.host}:{args.port}",
    ]
    print("[serve_code_docs] $ " + " ".join(cmd))
    return int(subprocess.call(cmd, cwd=str(rr), env=env))


if __name__ == "__main__":
    raise SystemExit(main())
