# CURRENT_STATE — OBSERVER

Last updated: 2026-01-26

Work Item: WI-0003
Result: PENDING

## p0

p0 — Execution runner: `scripts/execute.py` (paper broker) + lifecycle log
Parallelizzabile: NO
Allowlist (scrittura):
- scripts/execute.py
- src/execution/*
- src/db/*
- src/core/audit_engine.py (solo integrazioni minime)
Blocklist:
- Qualsiasi altro file
Azione:
- Leggi i canonici in `docs/` (single source-of-truth) per contesto.
- Usa `.doc/canonical/derived/` come sintesi operativa (se presente).
- Non modificare `docs/` salvo WI esplicitamente dedicati e in allowlist.
- Esegui il Work Item `WI-0003` in modo atomico.
- Se devi modificare file fuori Allowlist, fermati e proponi una variante di scope.
Acceptance:
- `py scripts/guardian.py lint` = PASS
- `py scripts/guardian.py next` aggiorna `.doc/CURRENT_STATE.md` quando cambia WI
Links:
- FR-09 (Execution)

## Completion protocol
Quando completi questo WI:
1) Aggiorna `.doc/TODO.md` mettendo `Status: DONE` per questo WI; oppure
2) Imposta qui `Result: DONE` e rilancia `py scripts/guardian.py next` per auto-close.
