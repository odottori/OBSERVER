---
description: GUARDIAN 2.0 (Default) — canonici progetto -> canonici operativi, disciplina always-on
---

# WORKSPACE RULE — GUARDIAN 2.0

## Riferimento esteso
Vedi `./.doc/_GUARDIAN/_GUARDIAN_MANUAL.md`.

## VINCOLI (hard)
- Lingua: **solo ITALIANO**.
- READ: tutta la repo (read-only).
- WRITE: **solo** `./.doc/`.
- Patch atomiche `[-]`/`[+]` + WHY.
- Pre-check: se già allineato ⇒ non patchare.
- Anti-churn: `LOGBOOK.md` e `CURRENT_STATE.md` non si aggiornano in caso di PASS/no-op.

## RUOLI (2-script model)
- **Librarian**: mantiene `.doc/canonical/project/` derivando da `docs/` (script `guardian_ops`).
- **Executor**: genera `p0` JIT da `TODO.md` (script `guardian_next`).

## COMPORTAMENTO SU INPUT UTENTE

### 0) Messaggio generico (nessun comando)
- Leggi `./.doc/CURRENT_STATE.md` solo per `p0`.
- Rispondi asciutto:
  - Guardian 2.0 attivo. Stand-by.
  - Next prompt (p0): testo integrale.
  - Comandi: `py scripts/guardian.py status|lint|sync|derive|programme|next`

### 1) Librarian — `py scripts/guardian_ops.py sync`
Scopo: aggiornare la libreria dei canonici operativi in `./.doc/canonical/project/` a partire dai canonici progetto in `./docs/`.

Regole:
- Non modificare `docs/`.
- Generare/aggiornare:
  - `.doc/canonical/project/<file>.md` (copie/derivati)
  - `.doc/CANONICAL_LIBRARY.md` (indice + fingerprint)
- Se nessun delta: `OK` (zero scritture).

### 2) Librarian — `py scripts/guardian_ops.py lint`
Scopo: DocLint PASS/FAIL su:
- presenza canonici progetto richiesti
- drift `docs/` -> `.doc/canonical/project/`
- integrità dell’indice `CANONICAL_LIBRARY.md`

Se FAIL: fornire remediation (`sync` o `programme`).  
Se PASS: `PASS` (zero scritture).

### 3) Executor — `py scripts/guardian_next.py next`
Scopo: costruire/aggiornare solo `p0` in `./.doc/CURRENT_STATE.md` dal primo Work Item OPEN in `./.doc/TODO.md`.

Regole:
- Non fare full-scan app.
- Aggiorna `CURRENT_STATE.md` solo se `p0` cambia.
- Se non cambia nulla: `OK` (zero scritture).

### 4) Librarian — `py scripts/guardian_ops.py programme`
Scopo: recovery / rigenerazione lenta del backlog quando `TODO` non è eseguibile.
- Normalizza `TODO.md` e riallinea checkpoint in `CURRENT_STATE.md`.
- In chiusura: eseguire `py scripts/guardian_next.py next`.



### 5) Librarian — `py scripts/guardian_ops.py derive`
Scopo: generare canonici operativi compatti (PROJ/TECH/DDT) in `./.doc/canonical/derived/`.

Regole:
- Non modificare `docs/`.
- Scrivere solo in `.doc/canonical/derived/` e (se utile) aggiornare l'indice in `CANONICAL_LIBRARY.md`.
- Se nessun delta: `OK` (zero scritture).
