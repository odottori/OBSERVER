#!/usr/bin/env python3
"""GUARDIAN RESET (standalone helper)

Uso (Windows / PowerShell):
- Reset "all'inizio" (riparti dal primo WI OPEN in TODO):
    py scripts/guardian_reset.py --mode start

- Reset su un WI specifico (es. WI-0001) e lo marca OPEN in TODO:
    py scripts/guardian_reset.py --mode wi --wi WI-0001

Cosa fa:
- Fa backup in `.doc/ops/backup/` di TODO/CURRENT_STATE/LOGBOOK (timestamp)
- Opzione start:
  - Imposta `Result: DONE` in CURRENT_STATE (se esiste) e poi elimina CURRENT_STATE
  - NON cambia gli Status nel TODO
- Opzione wi:
  - Marca il WI richiesto `Status: OPEN` nel TODO (rewrite conservativo)
  - Elimina CURRENT_STATE per forzare rigenerazione con `guardian next`

Nota:
- Non aggiunge comandi a `guardian.py`. È un tool di emergenza/ops.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re

DOC_ENCODING = "utf-8-sig"

WI_HEADER_RE = re.compile(r"^\s*(WI-(?P<num>\d{4}))\b", re.IGNORECASE)
STATUS_RE = re.compile(r"^\s*Status\s*:\s*(?P<status>[A-Z_]+)\s*$")


def read(path: Path) -> str:
    return path.read_text(encoding=DOC_ENCODING)


def write(path: Path, txt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding=DOC_ENCODING)


def backup(repo: Path, rel: str) -> None:
    p = repo / rel
    if not p.exists():
        return
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    bdir = repo / ".doc" / "ops" / "backup" / ts
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / Path(rel).name).write_text(read(p), encoding=DOC_ENCODING)


def set_wi_status(todo_text: str, wi_id: str, new_status: str) -> str:
    todo_text = todo_text.replace("\ufeff", "")
    lines = todo_text.splitlines()
    out = []
    i = 0
    changed = False
    target = wi_id.upper()

    while i < len(lines):
        line = lines[i]
        mh = WI_HEADER_RE.match(line)
        if mh and mh.group(1).upper() == target:
            out.append(lines[i])
            i += 1
            block = []
            while i < len(lines) and not WI_HEADER_RE.match(lines[i]):
                block.append(lines[i])
                i += 1
            status_done = False
            for bl in block:
                ms = STATUS_RE.match(bl)
                if ms and not status_done:
                    out.append(f"Status: {new_status}")
                    status_done = True
                    changed = True
                else:
                    out.append(bl)
            if not status_done:
                out.insert(len(out) - len(block), f"Status: {new_status}")
                changed = True
            continue

        out.append(line)
        i += 1

    if not changed:
        return todo_text
    return "\n".join(out) + ("\n" if todo_text.endswith("\n") else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["start", "wi"], required=True)
    ap.add_argument("--wi", default="")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    todo = repo / ".doc" / "TODO.md"
    cs = repo / ".doc" / "CURRENT_STATE.md"
    lb = repo / ".doc" / "LOGBOOK.md"

    if not todo.exists():
        print("FAIL: .doc/TODO.md mancante")
        return 2

    # backups
    backup(repo, ".doc/TODO.md")
    backup(repo, ".doc/CURRENT_STATE.md")
    backup(repo, ".doc/LOGBOOK.md")

    if args.mode == "start":
        # Soft reset: remove CURRENT_STATE so guardian next recomputes from TODO
        if cs.exists():
            # also mark Result DONE (best effort) before removing (audit)
            txt = read(cs)
            txt2 = re.sub(r"(?m)^Result:.*$", "Result: DONE", txt)
            write(cs, txt2)
            cs.unlink(missing_ok=True)
        print("DONE: reset start — CURRENT_STATE rimosso (riparti dal primo WI OPEN con guardian next).")
        return 0

    if args.mode == "wi":
        if not args.wi:
            print("FAIL: --wi richiesto in mode=wi")
            return 2
        wi_id = args.wi.upper()
        todo_text = read(todo)
        new_text = set_wi_status(todo_text, wi_id, "OPEN")
        write(todo, new_text)
        if cs.exists():
            cs.unlink(missing_ok=True)
        print(f"DONE: reset wi — {wi_id} marcato OPEN e CURRENT_STATE rimosso.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
