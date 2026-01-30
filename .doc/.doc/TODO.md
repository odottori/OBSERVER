# OBSERVER — TODO (Work Items)

> Patchpack milestone: **pianificazione granulare** (nessun refactor fisico).
> Data: 2026-01-30

## Nota operativa (scelta ragionevole)

L’inputpack fornito non includeva i file `.doc/TODO.md`, `.doc/LOGBOOK.md` né file di stato `CURRENT_STATE/`.

- `.doc/CURRENT_STATE.md` e `.doc/LOGBOOK.md` vengono quindi creati **come file veri** (baseline di governance).
- `.doc/TODO.md` viene fornito come baseline focalizzata su **WI-0107** (e su tranche/sotto-WI collegati).
  - Se nel repo canonico esiste già un TODO storico, applicare **merge manuale**: importare la sezione WI-0107 e i WI 0110..0160.

Questa scelta è tracciata in `CHANGELOG.md`.

---


## Stato (snapshot)

- PHASE1: **CLOSED** (docs/pdf/master rigenerati; `pytest` PASS) — confermato dal contesto.
- WI-0106 (docs-enabled): **DONE**.
- WI-0104 (refactor fisico per fasi): **BLOCKED** (vietato eseguire “in blocco”).

---

## Gate Suite (standard)

Ogni WI che tocca codice o docs deve usare gates ripetibili (minimo):

- **G0 Baseline**: `py -m pytest` (no-op check) + `py scripts/guardian.py lint`
- **G1 Import smoke**: `py -m compileall -q src` (se applicabile) + `py -c "import <pkg_root>; print('OK')"`
- **G2 Pytest**: `py -m pytest -q`
- **G3 Docs**: `py scripts/build_master_md.py`

Naming log (per WI):
- `reports/pytest_<WI>.log`
- `reports/guardian_lint_<WI>.log`
- `reports/build_master_md_<WI>.log`
- `reports/import_smoke_<WI>.log` (se usato)

---

# WI-0104 — Refactor fisico per fasi (EPIC)

**Status:** BLOCKED (non eseguire “in blocco”).

- Questo WI resta come *epic*, ma l’esecuzione viene spostata su tranche fisiche (WI-0120..0160).
- Il refactor fisico e’ consentito **solo** dopo chiusura WI-0107 + sotto-WI.

---

# WI-0107 — Refactor Plan (virtual)

## Scopo
Creare una fase intermedia prima del refactor fisico:

1) esplodere WI-0104 in TODO granulare (step piccoli + controlli successivi)
2) introdurre gates ripetibili e update canonici “a scaglioni”
3) produrre Move Map (virtual refactor) + import-shims plan + rollback plan
4) preparare tranche fisiche separate (1 tranche = 1 WI) con gate `pytest` PASS


## Allowlist (write)
- `.doc/TODO.md`
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`
- `docs/000_README_DOCSET.md`
- `scripts/build_master_md.py`
- `CHANGELOG.md`
- `reports/2026-01-30_WI-0107_planning.md`
- `.doc/CURRENT_STATE.md`
- `.doc/LOGBOOK.md`

## Blocklist (must not touch)
- `src/**`
- `tests/**`
- `mkdocs/**`
- `docs/LATEX_zip/**`
- `docs/*.pdf`

## DoD
- Creato `docs/012_REFACTOR_PLAN_VIRTUAL.md` con: Move Map, shims, deprecation policy, test strategy, expected logs, rollback.
- Aggiornato `.doc/TODO.md` con WI-0107 + sotto-WI granulari + tranche fisiche placeholder.
- Aggiornato `docs/000_README_DOCSET.md` e `scripts/build_master_md.py` per includere il nuovo canonico.
- `CHANGELOG.md` aggiornato con entry WI-0107 (planning-only).
- Evidenza in `reports/` + aggiornamento `.doc/CURRENT_STATE.md` e `.doc/LOGBOOK.md`.

## Gate
- G0 (baseline) — **atteso PASS** (nessun cambio codice).
- G3 (build master) — **atteso PASS** (include nuovo canonico).

## Evidence
- `reports/2026-01-30_WI-0107_planning.md`

---

## WI-0110 — Inventory & boundary map (virtual)

**Status:** DONE (2026-01-30)

**Scope:** solo analisi (no move).

### Output
- Lista *as-built* dei package/moduli per area (db/core/dataops/tools/pages).
- Mappa delle dipendenze cross-area (import graph “grezzo”).
- Identificazione del `pkg_root` reale (es. `observer`).

### DoD
- Sezione “Assunzioni e rischio” in `docs/012_REFACTOR_PLAN_VIRTUAL.md` aggiornata con snapshot as-built (blocco auto WI-0110).
- Creato report inventario in `reports/`.

### Gate
- G0 — **PASS** (pytest/guardian)

### Evidence
- `reports/WI-0110_inventory.md`
- `reports/pytest_WI-0110.log`
- `reports/guardian_lint_WI-0110.log`

### Allowlist
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`, `reports/**`, `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`, `.doc/LOGBOOK.md`

### Blocklist
- `src/**` (no move)


---

## WI-0111 — Move Map final (virtual)

**Status:** DONE (2026-01-30)

### Output
- Move Map completa (tabelle per tranche) con: as-is pattern, to-be target, fase, note.

### DoD
- Tabelle tranche 1..5 complete e coerenti.
- Identificati moduli “shared” e regole (PHASE0 utils).

### Gate
- G0

### Evidence
- `reports/WI-0111_move_map.md`
- `reports/pytest_WI-0111.log`
- `reports/guardian_lint_WI-0111.log`

### Allowlist
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`, `reports/**`, `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`

---

## WI-0112 — Import shims plan + deprecation policy

### Output
- Pattern shims (module/package) + criteri di rimozione + naming.
- Policy deprecazione (finestra + gate `-W error::DeprecationWarning`).

### DoD
- Strategia applicabile tranche-per-tranche.
- Policy esplicita e misurabile.

### Gate
- G0

### Evidence
- `reports/WI-0112_shims_policy.md`

### Allowlist
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`, `reports/**`, `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`

---

## WI-0113 — Rollback plan

### Output
- Protocollo di rollback per tranche (tag pre/post, reset vs revert).

### DoD
- Step “happy path” + “failure path” documentati.

### Gate
- G0

### Evidence
- `reports/WI-0113_rollback.md`

---

## WI-0114 — Gate protocol + expected logs

### Output
- Gate suite standardizzata (G0..G3) + naming log.

### DoD
- Sezione “Gate toolkit” + “Expected logs” in `docs/012_REFACTOR_PLAN_VIRTUAL.md` completa.

### Gate
- G0

### Evidence
- `reports/WI-0114_gates.md`

---

## WI-0115 — Skeleton tranche fisiche (TODO-only)

### Output
- Definizione WI-0120..0160 con DoD/Gate/Evidence/Allowlist/Blocklist.

### DoD
- Ogni tranche ha scope confinato ad 1 area.
- Ogni tranche ha gate `pytest -q` e log in `reports/`.

### Gate
- N/A (planning-only)

### Evidence
- Questa sezione nel TODO.

---

# Tranche fisiche (placeholder) — eseguibili solo dopo WI-0107/0110..0115

> Nota: i dettagli esatti (path e filelist) si finalizzano in WI-0110.

## WI-0120 — Refactor fisico tranche 1: db

### DoD
- Move fisico area db secondo Move Map.
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0120.log` + `reports/guardian_lint_WI-0120.log` + `reports/build_master_md_WI-0120.log` + `reports/import_smoke_WI-0120.log`

### Allowlist
- `src/**/db/**` (solo area db) + `src/**/compat/**` (shims)
- `tests/**` (solo se serve aggiornare import test)
- docs canonici consentiti: `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md` (solo se in allowlist tranche)

### Blocklist
- Move fuori area db

---

## WI-0130 — Refactor fisico tranche 2: core

### DoD
- Move fisico area core secondo Move Map.
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0130.log` + `reports/guardian_lint_WI-0130.log` + `reports/build_master_md_WI-0130.log` + `reports/import_smoke_WI-0130.log`

### Allowlist
- `src/**/core/**` (solo area core) + `src/**/compat/**` (shims)
- `tests/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area core

---

## WI-0140 — Refactor fisico tranche 3: dataops

### DoD
- Move fisico area dataops (incl. ingestion se ricade nell’area) secondo Move Map.
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0140.log` + `reports/guardian_lint_WI-0140.log` + `reports/build_master_md_WI-0140.log` + `reports/import_smoke_WI-0140.log`

### Allowlist
- `src/**/dataops/**` (+ `src/**/ingest/**` se presente) + `src/**/compat/**` (shims)
- `tests/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area dataops/ingest

---

## WI-0150 — Refactor fisico tranche 4: tools

### DoD
- Move fisico area tools secondo Move Map.
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0150.log` + `reports/guardian_lint_WI-0150.log` + `reports/build_master_md_WI-0150.log` + `reports/import_smoke_WI-0150.log`

### Allowlist
- `src/**/tools/**` (solo area tools) + `src/**/compat/**` (shims)
- `tests/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area tools

---

## WI-0160 — Refactor fisico tranche 5: pages

### DoD
- Move fisico area pages secondo Move Map (package `src/**/pages/**` o root `pages/**`).
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0160.log` + `reports/guardian_lint_WI-0160.log` + `reports/build_master_md_WI-0160.log` + `reports/import_smoke_WI-0160.log`

### Allowlist
- `src/**/pages/**` e/o `pages/**` (solo area pages) + `src/**/compat/**` (shims)
- `tests/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area pages
