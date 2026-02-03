#!/usr/bin/env python3
"""GUARDIAN 2.1 — Executor / JIT Prompt (NEXT)

Obiettivi:
- Seleziona un Work Item (WI) OPEN da ./.doc/TODO.md
- Genera/aggiorna p0 in ./.doc/CURRENT_STATE.md
- Appende un record in ./.doc/LOGBOOK.md per resilienza (crash-safe)
- Scrive SOLO in ./.doc/

Fix chiave (stabilità):
- Resume solo se il WI in CURRENT_STATE risulta ancora OPEN nel TODO.
- Se CURRENT_STATE è stale (WI non OPEN nel TODO), viene ignorato automaticamente.
- Se la selezione WI cambia, forziamo la scrittura di CURRENT_STATE anche in caso di confronto "unchanged" (difesa contro edge-case di encoding/newlines).
- Logbook include diagnostica minima (old_id, active_id, selected_id, status).

Compatibilità:
- Parsing WI robusto (NBSP/BOM/tabs; header varianti; CRLF/LF).
- Encoding file operativi: UTF-8 con BOM (utf-8-sig) per compatibilità Windows.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

# ----------------------------
# IO helpers (Windows-friendly)
# ----------------------------

DOC_ENCODING = "utf-8-sig"  # UTF-8 con BOM: leggibile out-of-the-box in Windows PowerShell/Notepad


def _read_text(path: Path) -> str:
    return path.read_text(encoding=DOC_ENCODING)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # EOL determinism: avoid CRLF/LF churn on Windows.
    with path.open("w", encoding=DOC_ENCODING, newline="\n") as f:
        f.write(content)


def write_if_changed(path: Path, content: str, *, force: bool = False) -> bool:
    """Anti-churn: scrive solo se il contenuto cambia.

    Se force=True, scrive comunque (usato quando la selezione WI cambia, come safeguard).
    """
    if not force and path.exists():
        try:
            old = _read_text(path)
            if old == content:
                return False
        except Exception:
            # Se non leggibile (raro), sovrascrivi.
            pass
    _write_text(path, content)
    return True


# ----------------------------
# WI parsing
# ----------------------------

WI_HEADER_RE = re.compile(r"^\s*(WI-(?P<num>\d{4}))\b(?:\s*(?:(?:—|-|:)\s*)?(?P<title>.*))?$")
STATUS_RE = re.compile(r"^\s*Status\s*:\s*(?P<status>[A-Z_]+)\s*$")

# Legacy support: single-line bullets like "- [OPEN] title"
LEGACY_BULLET_RE = re.compile(r"^\s*[-*]\s*\[(?P<status>OPEN|DONE)\]\s*(?P<title>.+)\s*$")

SECTION_RE = re.compile(r"^\s*(?P<name>Allowlist|Blocklist|Acceptance|DoD|Gate|Scope|Links)\s*:\s*$", re.IGNORECASE)


@dataclass
class WorkItem:
    wi_id: str
    title: str
    status: str
    allowlist: List[str]
    blocklist: List[str]
    acceptance: List[str]
    gate: List[str]
    links: List[str]
    raw_block: str


def _collect_list(block_lines: List[str], section_name: str) -> List[str]:
    out: List[str] = []
    in_section = False
    for line in block_lines:
        m = SECTION_RE.match(line)
        if m:
            in_section = (m.group("name").lower() == section_name.lower())
            continue
        if in_section:
            if line.strip() == "":
                break
            # stop if another section begins
            if SECTION_RE.match(line):
                break
            s = line.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
            elif s.startswith("* "):
                out.append(s[2:].strip())
    return [x for x in out if x]


def parse_work_items(todo_text: str) -> List[WorkItem]:
    """Parse WI blocks.

    Regole:
    - Header riconosciuto se la riga (strip) inizia con 'WI-####' (con titolo opzionale)
    - Il blocco è fino al prossimo header WI-#### o EOF
    - Status è letto da riga 'Status: ...' nel blocco
    - Supporto legacy: '- [OPEN] ...' come WI auto
    """
    todo_text = (
        todo_text
        .replace("\ufeff", "")
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\t", " ")
    )
    lines = todo_text.splitlines()

    wis: List[WorkItem] = []
    i = 0
    auto_idx = 1

    while i < len(lines):
        line = lines[i]
        mh = WI_HEADER_RE.match(line)
        if mh:
            wi_id = mh.group(1).strip().upper()
            title = (mh.group("title") or "").strip()
            if not title:
                title = wi_id

            # block until next header
            block_lines = [lines[i]]
            j = i + 1
            while j < len(lines) and not WI_HEADER_RE.match(lines[j]):
                block_lines.append(lines[j])
                j += 1

            status = "UNKNOWN"
            for bl in block_lines:
                ms = STATUS_RE.match(bl)
                if ms:
                    status = ms.group("status").strip().upper()
                    break

            allowlist = _collect_list(block_lines, "Allowlist")
            blocklist = _collect_list(block_lines, "Blocklist")
            acceptance = _collect_list(block_lines, "Acceptance")
            gate = _collect_list(block_lines, "Gate")
            links = _collect_list(block_lines, "Links")

            wis.append(
                WorkItem(
                    wi_id=wi_id,
                    title=title,
                    status=status,
                    allowlist=allowlist,
                    blocklist=blocklist,
                    acceptance=acceptance,
                    gate=gate,
                    links=links,
                    raw_block="\n".join(block_lines).strip(),
                )
            )
            i = j
            continue

        mb = LEGACY_BULLET_RE.match(line)
        if mb:
            st = mb.group("status").strip().upper()
            title = mb.group("title").strip()
            wi_id = f"WI-AUTO-{auto_idx:04d}"
            auto_idx += 1
            wis.append(
                WorkItem(
                    wi_id=wi_id,
                    title=title,
                    status=st,
                    allowlist=[],
                    blocklist=[],
                    acceptance=[],
                    gate=[],
                    links=[],
                    raw_block=line.strip(),
                )
            )
        i += 1

    return wis


# ----------------------------
# CURRENT_STATE / resume logic
# ----------------------------

ACTIVE_WI_RE = re.compile(r"\b(WI-\d{4})\b")
RESULT_RE = re.compile(r"^\s*Result\s*:\s*(?P<res>[A-Z_]+)\s*$", re.IGNORECASE)


def extract_active_wi_id(current_state_text: str) -> Optional[str]:
    m = re.search(r"^\s*Work\s+Item\s*:\s*(WI-\d{4})\b", current_state_text, re.IGNORECASE | re.MULTILINE)
    if m:
        return m.group(1).upper()
    m2 = ACTIVE_WI_RE.search(current_state_text)
    return m2.group(1).upper() if m2 else None


def extract_result(current_state_text: str) -> Optional[str]:
    for line in current_state_text.splitlines():
        m = RESULT_RE.match(line)
        if m:
            return m.group("res").upper()
    return None


# ----------------------------
# TODO mutation (auto-close from CURRENT_STATE)
# ----------------------------


def mark_wi_done_in_todo(todo_text: str, wi_id: str) -> str:
    """Mark Status: DONE inside the WI block for wi_id (conservative rewrite)."""
    todo_text_norm = (
        todo_text
        .replace("\ufeff", "")
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\t", " ")
    )
    lines = todo_text_norm.splitlines()
    out: List[str] = []
    i = 0
    changed = False

    while i < len(lines):
        line = lines[i]
        mh = WI_HEADER_RE.match(line)
        if mh and mh.group(1).strip().upper() == wi_id.upper():
            out.append(lines[i])
            i += 1

            status_replaced = False
            block_lines: List[str] = []
            while i < len(lines) and not WI_HEADER_RE.match(lines[i]):
                block_lines.append(lines[i])
                i += 1

            for bl in block_lines:
                ms = STATUS_RE.match(bl)
                if ms and not status_replaced:
                    out.append("Status: DONE")
                    status_replaced = True
                    changed = True
                else:
                    out.append(bl)

            if not status_replaced:
                out.insert(len(out) - len(block_lines), "Status: DONE")
                changed = True
            continue

        out.append(line)
        i += 1

    if not changed:
        return todo_text
    return "\n".join(out) + ("\n" if todo_text.endswith("\n") else "")


def set_wi_status_in_todo(todo_text: str, wi_id: str, new_status: str) -> str:
    todo_text_norm = (
        todo_text
        .replace("\ufeff", "")
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\t", " ")
    )
    lines = todo_text_norm.splitlines()
    out: List[str] = []
    i = 0
    changed = False
    new_status = str(new_status).strip().upper()

    while i < len(lines):
        line = lines[i]
        mh = WI_HEADER_RE.match(line)
        if mh and mh.group(1).strip().upper() == wi_id.upper():
            out.append(lines[i])
            i += 1

            status_replaced = False
            block_lines: List[str] = []
            while i < len(lines) and not WI_HEADER_RE.match(lines[i]):
                block_lines.append(lines[i])
                i += 1

            for bl in block_lines:
                ms = STATUS_RE.match(bl)
                if ms and not status_replaced:
                    out.append(f"Status: {new_status}")
                    status_replaced = True
                    changed = True
                else:
                    out.append(bl)

            if not status_replaced:
                out.insert(len(out) - len(block_lines), f"Status: {new_status}")
                changed = True
            continue

        out.append(line)
        i += 1

    if not changed:
        return todo_text
    return "\n".join(out) + ("\n" if todo_text.endswith("\n") else "")


# ----------------------------
# p0 builder
# ----------------------------


def build_current_state(wi: WorkItem, canon_dirname: str) -> str:
    today = date.today().isoformat()

    allowlist = wi.allowlist or [
        "scripts/guardian.py",
        "scripts/guardian_next.py",
        "scripts/guardian_ops.py",
        ".doc/TODO.md",
        ".doc/CURRENT_STATE.md",
        ".doc/LOGBOOK.md",
        ".doc/_GUARDIAN/templates/*",
    ]
    blocklist = wi.blocklist or ["Qualsiasi altro file"]

    acceptance = wi.acceptance or [
        "`py scripts/guardian.py lint` = PASS",
        "`py scripts/guardian.py next` aggiorna `.doc/CURRENT_STATE.md` quando cambia WI",
    ]

    p0_lines: List[str] = []
    p0_lines.append("# CURRENT_STATE — OBSERVER")
    p0_lines.append("")
    p0_lines.append(f"Last updated: {today}")
    p0_lines.append("")
    p0_lines.append(f"Work Item: {wi.wi_id}")
    p0_lines.append("Result: PENDING")
    p0_lines.append("")
    p0_lines.append("## p0")
    p0_lines.append("")
    p0_lines.append(f"p0 — {wi.title}")
    p0_lines.append("Parallelizzabile: NO")
    p0_lines.append("Allowlist (scrittura):")
    for a in allowlist:
        p0_lines.append(f"- {a}")
    p0_lines.append("Blocklist:")
    for b in blocklist:
        p0_lines.append(f"- {b}")
    p0_lines.append("Azione:")
    p0_lines.append("- Leggi i canonici in `docs/` (single source-of-truth) per contesto.")
    p0_lines.append(f"- Usa `.doc/{canon_dirname}/derived/` come sintesi operativa (se presente).")
    p0_lines.append("- Non modificare `docs/` salvo WI esplicitamente dedicati e in allowlist.")
    p0_lines.append(f"- Esegui il Work Item `{wi.wi_id}` in modo atomico.")
    p0_lines.append("- Se devi modificare file fuori Allowlist, fermati e proponi una variante di scope.")
    p0_lines.append("Acceptance:")
    for a in acceptance:
        p0_lines.append(f"- {a}")
    if wi.gate:
        p0_lines.append("Gate (esegui e conserva output in LOGBOOK):")
        for g in wi.gate:
            p0_lines.append(f"- {g}")
    if wi.links:
        p0_lines.append("Links:")
        for l in wi.links:
            p0_lines.append(f"- {l}")

    p0_lines.append("")
    p0_lines.append("## Completion protocol")
    p0_lines.append("Quando completi questo WI:")
    p0_lines.append("1) Aggiorna `.doc/TODO.md` mettendo `Status: DONE` per questo WI; oppure")
    p0_lines.append("2) Imposta qui `Result: DONE` e rilancia `py scripts/guardian.py next` per auto-close.")
    p0_lines.append("")

    return "\n".join(p0_lines)


def append_logbook(logbook_path: Path, message: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"\n## {ts}\n{message.strip()}\n"
    if logbook_path.exists():
        old = _read_text(logbook_path)
    else:
        old = "# LOGBOOK — OBSERVER\n\n"
    _write_text(logbook_path, old + entry)


def _wi_status_map(wis: List[WorkItem]) -> dict[str, str]:
    return {w.wi_id.upper(): w.status.upper() for w in wis}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="guardian", add_help=True)
    ap.add_argument("command", choices=["next"], help="Generate / update CURRENT_STATE from TODO")
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    docdir = repo_root / ".doc"
    if (docdir / "canonical").exists():
        canon_dirname = "canonical"
    elif (docdir / "canon").exists():
        canon_dirname = "canon"
    else:
        canon_dirname = "canonical"

    todo_path = repo_root / ".doc" / "TODO.md"
    current_state_path = repo_root / ".doc" / "CURRENT_STATE.md"
    logbook_path = repo_root / ".doc" / "LOGBOOK.md"

    if not todo_path.exists():
        print("FAIL: `.doc/TODO.md` mancante. Eseguire init per creare struttura.")
        return 2

    todo_text = todo_path.read_text(encoding=DOC_ENCODING)
    wis = parse_work_items(todo_text)
    status_map = _wi_status_map(wis)

    # Read CURRENT_STATE if present
    current_text = ""
    old_id: Optional[str] = None
    active_id: Optional[str] = None
    res: Optional[str] = None

    if current_state_path.exists():
        try:
            current_text = _read_text(current_state_path)
            old_id = extract_active_wi_id(current_text)
            active_id = old_id
            res = extract_result(current_text)
        except Exception:
            current_text = ""
            old_id = None
            active_id = None
            res = None

    # Auto-close hook: if CURRENT_STATE says Result: DONE, mark TODO and move on.
    if active_id and current_text and res == "DONE":
        new_todo = mark_wi_done_in_todo(todo_text, active_id)
        if new_todo != todo_text:
            _write_text(todo_path, new_todo)
            append_logbook(logbook_path, f"Auto-closed {active_id}: set Status: DONE in TODO via CURRENT_STATE.Result=DONE.")
            todo_text = new_todo
            wis = parse_work_items(todo_text)
            status_map = _wi_status_map(wis)
        else:
            append_logbook(logbook_path, f"Requested auto-close for {active_id}, but TODO block not updated (format mismatch).")

    # Resume eligibility: active WI must be OPEN in TODO.
    if active_id:
        st = status_map.get(active_id.upper(), "UNKNOWN")
        if st != "OPEN":
            append_logbook(logbook_path, f"Stale CURRENT_STATE: {active_id} is {st} in TODO; ignoring resume.")
            active_id = None

    # Select WI
    wi_selected: Optional[WorkItem] = None
    if active_id:
        for w in wis:
            if w.wi_id.upper() == active_id.upper() and w.status.upper() == "OPEN":
                wi_selected = w
                break

    if wi_selected is None:
        for w in wis:
            if w.status.upper() == "OPEN":
                wi_selected = w
                break

    if wi_selected is None:
        promote: Optional[WorkItem] = None
        for w in wis:
            if w.status.upper() in {"PENDING", "QUEUED"}:
                promote = w
                break

        if promote is not None:
            new_todo = set_wi_status_in_todo(todo_text, promote.wi_id, "OPEN")
            if new_todo != todo_text:
                _write_text(todo_path, new_todo)
                append_logbook(logbook_path, f"Auto-promoted {promote.wi_id}: set Status: OPEN in TODO (fallback from no OPEN WI).")
                todo_text = new_todo
                wis = parse_work_items(todo_text)
                status_map = _wi_status_map(wis)

            for w in wis:
                if w.wi_id.upper() == promote.wi_id.upper() and w.status.upper() == "OPEN":
                    wi_selected = w
                    break

    if not wi_selected:
        print("OK: nessun Work Item OPEN trovato (o backlog non conforme).")
        append_logbook(logbook_path, "No OPEN WI found (or backlog non conformant).")
        return 0

    selected_id = wi_selected.wi_id

    # Build output
    content = build_current_state(wi_selected, canon_dirname)

    # Safeguard: if selection changed, force write (even if compare says unchanged)
    force_write = (old_id is not None and old_id.upper() != selected_id.upper())
    updated = write_if_changed(current_state_path, content, force=force_write)

    # Diagnostics (always logged)
    diag = f"next: old_id={old_id or 'NONE'} active_id={(active_id or 'NONE')} selected_id={selected_id} selected_status={wi_selected.status}"

    if updated:
        print(f"DONE: p0 aggiornato per {selected_id}.")
        append_logbook(logbook_path, diag + " | CURRENT_STATE updated.")
    else:
        print("OK: p0 invariato (no-op).")
        append_logbook(logbook_path, diag + " | no-op (unchanged).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
