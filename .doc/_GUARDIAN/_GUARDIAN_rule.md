---
trigger: always_on
---

## SYSTEM RULE: GUARDIAN 2.0 PROTOCOL

### Riferimento esteso
Vedi: `./.doc/_GUARDIAN/_GUARDIAN_MANUAL.md`.

## SCOPE (hard)
- READ: tutta la repo (read-only).
- WRITE: **solo** `./.doc/` (salvo richiesta utente esplicita).
- Lingua: **solo ITALIANO**.

### Doc Governance (hard)
- I **canonici** restano solo in `docs/` (e `.doc/` solo per derivati GUARDIAN).
- `mkdocs/` è **vista derivata**: vietato creare/tenere copie manuali dei canonici in `mkdocs/docs/`.
- Ammessa in MkDocs solo la copia di **artefatti non canonici** (es. PDF) se sincronizzata via script.

## Anti-churn (hard)
- Se l’esito è `OK` o `PASS`, **non** aggiornare `./.doc/LOGBOOK.md` e `./.doc/CURRENT_STATE.md`.

## Dual-Agent (hard)
Quando può esistere patch su `.doc/`: output in due sezioni:
- **[ESECUTORE]** evidenze + proposta patch
- **[CRITICO]** verifica scettica (no legacy, no inferenze, no patch ridondanti)

## Canonici (hard)
- Canonici di progetto (input): `./docs/`
- Canonici operativi (output): `./.doc/canonical/project/` (copie canonici progetto) e `./.doc/canonical/derived/` (canonici compatti)
- Indice: `./.doc/CANONICAL_LIBRARY.md`

## Messaggi generici (nessun comando)
- Leggi `./.doc/CURRENT_STATE.md` **solo** per `p0`.
- Rispondi in max 3 righe:
  - Guardian 2.0 attivo. Stand-by.
  - Next prompt (p0): <testo integrale>
  - Comandi: `py scripts/guardian.py status|lint|sync|derive|programme|next`

## Comandi “guardian” (mappati a script)
- Wrapper (consigliato): `py scripts/guardian.py <comando>` (help: `py scripts/guardian.py`)
- Librarian (diretto): `py scripts/guardian_ops.py init|sync|derive|lint|programme|status`
- Executor (diretto): `py scripts/guardian_next.py next`
