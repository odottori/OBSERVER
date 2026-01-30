"""
MKDocs-docs contract checker

Se passa, hai una prova meccanica che:
- MkDocs non contiene copie canoniche proibite
- gli stub sono stub
- la vista è davvero “appesa” ai canonici

esempio:
PS C:\Users\odott\Documents\OBSERVER> py .\scripts\docs_contract_check.py
[CONTRACT OK] mkdocs is view-only; canonicals stay in docs/; stubs use includes.

"""
#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
MK = ROOT / "mkdocs" / "docs"

FORBIDDEN_EXACT = {
    "010_MODULE_REGISTRY.md",
    "011_GAP_DERIVATION_MATRIX.md",
}

def fail(msg: str) -> int:
    print("[CONTRACT FAIL]", msg)
    return 2

def main() -> int:
    if not MK.exists():
        return fail("mkdocs/docs not found")

    # 1) No forbidden canonical copies in mkdocs
    for p in MK.rglob("*.md"):
        if p.name in FORBIDDEN_EXACT:
            return fail(f"Forbidden canonical copy in mkdocs: {p}")

    # 2) Docset stubs must be pure includes (no content duplication)
    docset = MK / "docset"
    if docset.exists():
        for p in docset.glob("0*.md"):
            txt = p.read_text(encoding="utf-8", errors="replace").strip()
            if '--8<-- "docs/' not in txt:
                return fail(f"Docset page is not an include-stub: {p}")

    # 3) Registry/gaps stubs must include canonical docs
    must_include = [
        MK / "modules" / "registry.md",
        MK / "gaps" / "register.md",
        MK / "gaps" / "derived.md",
    ]
    for p in must_include:
        if not p.exists():
            return fail(f"Missing required stub: {p}")
        txt = p.read_text(encoding="utf-8", errors="replace")
        if '--8<-- "docs/' not in txt:
            return fail(f"Required stub does not include docs/: {p}")

    print("[CONTRACT OK] mkdocs is view-only; canonicals stay in docs/; stubs use includes.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
