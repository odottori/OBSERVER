#!/usr/bin/env python3
"""Build a single 'master' Markdown document for the OBSERVER docset.

Output:
- docs/OBSERVER_v1.2.5.md

Windows / PowerShell:
  py scripts\build_master_md.py
"""

from __future__ import annotations
from pathlib import Path

DOCS = Path("docs")
OUT = DOCS / "OBSERVER_v1.2.5.md"

CANON = [
    "000_README_DOCSET.md",
    "001_PROJECT_OVERVIEW.md",
    "002_PDR_OBSERVER.md",
    "003_PDD_OBSERVER.md",
    "004_DDT_DATADICTIONARY.md",
    "005_TRACEABILITY_MATRIX.md",
    "006_REPO_BOM.md",
    "007_PARAMETER_SNAPSHOT.md",
    "008_EVIDENCE_PACK.md",
    "009_GAP_REGISTER.md",
    "010_MODULE_REGISTRY.md",
    "012_REFACTOR_PLAN_VIRTUAL.md",
]

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace").strip()

def main() -> None:
    parts: list[str] = []
    parts.append("# OBSERVER 2.0 — Docset v1.2.5 (Markdown)\n")
    parts.append("> Auto-assembled from the canonical documents in `docs/`.\n")
    parts.append("\n---\n")

    for name in CANON:
        p = DOCS / name
        parts.append(f"## {name}\n")
        parts.append(read(p) if p.exists() else "*(missing)*")
        parts.append("\n\n---\n")

    specs_dir = DOCS / "specs"
    if specs_dir.exists():
        parts.append("# Technical Specs (docs/specs)\n")
        for sp in sorted(specs_dir.glob("*.md")):
            parts.append(f"## {sp.relative_to(DOCS)}\n")
            parts.append(read(sp))
            parts.append("\n\n---\n")

    OUT.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
    print(f"OK -> {OUT}")

if __name__ == "__main__":
    main()
