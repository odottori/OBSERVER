#!/usr/bin/env python3
"""
Generate MkDocs derived pages (module cards) from canonical docs.

Contracts (hard):
- Canonical docs live only in `docs/`
- MkDocs is a derived view: generated pages live under `mkdocs/docs/modules/_generated/`
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
MKDOCS_DOCS = REPO / "mkdocs" / "docs"

REGISTRY = DOCS / "010_MODULE_REGISTRY.md"
OUT_DIR = MKDOCS_DOCS / "modules" / "_generated"


def slugify_anchor(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def parse_module_blocks(md: str):
    pattern = re.compile(
        r"^###\s+(MOD-[A-Z0-9\-]+)\s*\n(?P<body>.*?)(?=^###\s+MOD-[A-Z0-9\-]+\s*$|\Z)",
        re.M | re.S,
    )
    for m in pattern.finditer(md):
        yield m.group(1).strip(), m.group("body").strip()


def parse_field(body: str, label: str) -> str | None:
    m = re.search(rf"^\-\s+\*\*{re.escape(label)}\*\*:\s*(.+)$", body, re.M)
    return m.group(1).strip() if m else None


def extract_gaps(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bGAP-[A-Z0-9\-]+\b", text)))


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str) -> None:
    # EOL determinism: avoid CRLF/LF churn on Windows.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(content.strip() + "\n")


def module_page(mod_id: str, body: str) -> str:
    dominio = parse_field(body, "Dominio") or ""
    livello = parse_field(body, "Livello") or ""
    phase = parse_field(body, "PHASE") or ""
    entry = parse_field(body, "Entrypoint") or ""
    codice = parse_field(body, "Codice") or ""
    output = parse_field(body, "Output") or ""
    gate = parse_field(body, "Gate minimi") or ""
    gap_note = parse_field(body, "Gap derivati") or ""

    gaps = extract_gaps(body + "\n" + gap_note)

    anchor = slugify_anchor(mod_id)
    canon_link = f"../registry/#" + anchor

    lines: list[str] = []
    lines.append(f"# {mod_id}")
    lines.append("")
    lines.append(f"**Registro canonico:** [{mod_id}]({canon_link})")
    lines.append("")
    if dominio:
        lines.append(f"- **Dominio:** {dominio}")
    if livello:
        lines.append(f"- **Livello:** {livello}")
    if phase:
        lines.append(f"- **PHASE:** {phase}")
    if entry:
        lines.append(f"- **Entrypoint:** `{entry}`")
    if codice:
        lines.append(f"- **Codice:** `{codice}`")
    if output:
        lines.append(f"- **Output:** `{output}`")
    if gate:
        lines.append(f"- **Gate minimi:** {gate}")
    if gap_note:
        lines.append(f"- **Gap derivati (nota):** {gap_note}")

    if gaps:
        lines.append("")
        lines.append("## Gap collegati")
        for g in gaps:
            g_anchor = slugify_anchor(g)
            lines.append(f"- [{g}](../../gaps/register/#" + g_anchor + ")")

    lines.append("")
    lines.append("## Nota")
    lines.append("Questa pagina è **derivata**: viene generata da `docs/010_MODULE_REGISTRY.md`.")
    return "\n".join(lines)


def index_page(mods: list[tuple[str, str]]) -> str:
    rows = ["| Modulo | PHASE | Dominio | Livello | Gap |", "|---|---:|---|---:|---|"]
    for mod_id, body in mods:
        dominio = parse_field(body, "Dominio") or ""
        livello = parse_field(body, "Livello") or ""
        phase = parse_field(body, "PHASE") or ""
        gaps = extract_gaps(body)
        gap_cell = ", ".join(gaps) if gaps else ""
        rows.append(f"| [{mod_id}]({mod_id}.md) | {phase} | {dominio} | {livello} | {gap_cell} |")

    return "\n".join([
        "# Schede moduli (generate)",
        "",
        "Indice navigabile per modulo. Le schede sono **generate** dal registro canonico.",
        "",
        *rows,
        "",
        "## Fonte",
        "- `docs/010_MODULE_REGISTRY.md`",
    ])




def phase_page(phase: str, mods: list[tuple[str, str]]) -> str:
    rows = ["| Modulo | Dominio | Livello | Gap |", "|---|---|---:|---|"]
    for mod_id, body in mods:
        ph = (parse_field(body, "PHASE") or "").strip().upper()
        if ph != phase.upper():
            continue
        dominio = parse_field(body, "Dominio") or ""
        livello = parse_field(body, "Livello") or ""
        gaps = extract_gaps(body)
        gap_cell = ", ".join(gaps) if gaps else ""
        rows.append(f"| [{mod_id}]({mod_id}.md) | {dominio} | {livello} | {gap_cell} |")

    return "\n".join([
        f"# {phase}",
        "",
        "Elenco moduli aggregati per PHASE (pagina derivata).",
        "",
        *rows,
        "",
        "## Fonte",
        "- `docs/010_MODULE_REGISTRY.md`",
    ])
def main() -> int:
    if not REGISTRY.exists():
        print(f"[gen_mkdocs_views] missing {REGISTRY}")
        return 2

    md = REGISTRY.read_text(encoding="utf-8", errors="replace")
    mods = list(parse_module_blocks(md))
    if not mods:
        print("[gen_mkdocs_views] no modules found (expected headings '### MOD-...')")
        return 3

    ensure_dir(OUT_DIR)

    for mod_id, body in mods:
        write_file(OUT_DIR / f"{mod_id}.md", module_page(mod_id, body))

    write_file(OUT_DIR / "index.md", index_page(mods))

    # Aggregate by PHASE
    write_file(OUT_DIR / "PHASE1.md", phase_page("PHASE1", mods))
    write_file(OUT_DIR / "PHASE2.md", phase_page("PHASE2", mods))

    print(f"[gen_mkdocs_views] OK: {len(mods)} module pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
