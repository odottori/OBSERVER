#!/usr/bin/env python3
"""make_ai_input_pack.py

Create a deterministic ZIP "input pack" containing the exact repo files ChatGPT needs.

Usage (from repo root):
  py scripts/make_ai_input_pack.py --out OBSERVER_AI_INPUTPACK.zip

Optional:
  py scripts/make_ai_input_pack.py --out OBSERVER_AI_INPUTPACK.zip --with-requirements

Notes:
- The ZIP preserves relative paths (e.g., docs/..., scripts/...).
- It excludes .venv, __pycache__, .pytest_cache by design.
"""

from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

DEFAULT_FILES = [
    "docs/002_PDR_OBSERVER.md",
    "docs/004_DDT_DATADICTIONARY.md",
    "docs/005_TRACEABILITY_MATRIX.md",
    "docs/010_MODULE_REGISTRY.md",
    "docs/OBSERVER_v1.2.5.md",
    "docs/000_README_DOCSET.md",
    "scripts/build_master_md.py",
    "CHANGELOG.md",
]

DEFAULT_REQUIREMENTS = """# Core
pandas>=2.0
numpy>=1.24
duckdb>=1.0
tabulate>=0.9

# UI
streamlit>=1.31
matplotlib>=3.7

# Optional ingestion
requests>=2.31
yfinance>=0.2.33

# Testing
pytest>=7.4
"""

def add_file(z: zipfile.ZipFile, repo_root: Path, rel: str) -> None:
    p = (repo_root / rel).resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(rel)
    # Store with forward slashes for portability
    arcname = rel.replace("\\", "/")
    z.write(p, arcname)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output zip path")
    ap.add_argument("--with-requirements", action="store_true", help="Include requirements.txt (create if missing)")
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES, help="Override file list")
    args = ap.parse_args()

    repo_root = Path.cwd()
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Optionally ensure requirements.txt exists (without touching repo unless requested)
    tmp_req = None
    if args.with_requirements:
        req_path = repo_root / "requirements.txt"
        if req_path.exists():
            pass
        else:
            # Create temporary requirements content and include it (without writing to repo).
            tmp_req = DEFAULT_REQUIREMENTS

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for rel in args.files:
            add_file(z, repo_root, rel)

        if args.with_requirements:
            req_path = repo_root / "requirements.txt"
            if req_path.exists():
                add_file(z, repo_root, "requirements.txt")
            else:
                z.writestr("requirements.txt", tmp_req)

        # Add a paths manifest
        manifest = "\n".join(["Included paths:"] + [f"- {p}" for p in args.files] + (["- requirements.txt"] if args.with_requirements else [])) + "\n"
        z.writestr("PATCHPACK_PATHS.txt", manifest)

    print(f"OK: wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
