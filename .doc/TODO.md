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
- **G2 Pytest**: `py -m pytest -q -W error::DeprecationWarning`
- **G3 Docs**: `py scripts/build_master_md.py`

Naming log (per WI):
- `reports/pytest_<WI>.log`
- `reports/guardian_lint_<WI>.log`
- `reports/build_master_md_<WI>.log`
- `reports/import_smoke_<WI>.log` (se usato)

Nota (preferred): per i WI standard usare il one-command runner:
- `py scripts/guardian.py gate --wi WI-XXXX --mode normal` (scrive 7 log + esegue `collect`)

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
- `test/**`
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
- `.doc/CANONICAL_LIBRARY.md`
- `.doc/canonical/derived/DDT.md`
- `.doc/canonical/derived/PROJ.md`
- `.doc/canonical/derived/TECH.md`
- `docs/OBSERVER_v1.2.5.md`
- `reports/2026-02-03_WI-0240_CLOSE.md`

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

**Status:** DONE (2026-01-30)

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
- `reports/pytest_WI-0112.log`
- `reports/guardian_lint_WI-0112.log`

### Allowlist
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`, `reports/**`, `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`

---

## WI-0113 — Rollback plan

**Status:** DONE (2026-01-30)

### Output
- Protocollo di rollback per tranche (tag pre/post, reset vs revert).

### DoD
- Step “happy path” + “failure path” documentati.
- Matrice decisionale (reset vs revert) e naming tag per tranche.
- Evidenza presente in `reports/`.

### Gate
- G0

### Evidence
- `reports/WI-0113_rollback.md`
- `reports/pytest_WI-0113.log`
- `reports/guardian_lint_WI-0113.log`
### Allowlist
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`, `reports/**`, `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`

### Blocklist
- `src/**`, `test/**` (no change)

---

## WI-0114 — Gate protocol + expected logs

**Status:** DONE (2026-01-30)

### Output
- Gate suite standardizzata (G0..G3) + naming log.

### DoD
- Sezione “Gate toolkit” + “Expected logs” in `docs/012_REFACTOR_PLAN_VIRTUAL.md` completa.
- Report di evidenza in `reports/`.

### Gate
- G0 — PASS (pytest/guardian)

### Evidence
- `reports/WI-0114_gates.md`
- `reports/pytest_WI-0114.log`
- `reports/guardian_lint_WI-0114.log`

### Allowlist
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`, `reports/**`, `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`

### Blocklist
- `src/**`, `test/**` (no change)

---

## WI-0115 — Skeleton tranche fisiche (TODO-only)

**Status:** DONE (2026-01-30)


### Output
- Definizione WI-0120..0160 con DoD/Gate/Evidence/Allowlist/Blocklist.

### DoD
- Ogni tranche ha scope confinato ad 1 area.
- Ogni tranche ha gate `pytest -q` e log in `reports/`.

### Gate
- G0 — PASS (pytest/guardian)

### Evidence
- `.doc/TODO.md` (sezione WI-0115 + tranche WI-0120..0160)
- `reports/pytest_WI-0115.log`
- `reports/guardian_lint_WI-0115.log`

### Allowlist
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`

### Blocklist
- `src/**`, `test/**`, `docs/**` (no change)

---

# Tranche fisiche (placeholder) — eseguibili solo dopo WI-0107/0110..0115

> Nota: i dettagli esatti (path e filelist) si finalizzano in WI-0110.

## WI-0120 — Refactor fisico tranche 1: db

**Status:** CLOSED (gates PASS — pytest 57 passed, 3 warnings; guardian PASS)

### DoD
- Move fisico area db secondo Move Map.
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0120.log` + `reports/guardian_lint_WI-0120.log` + `reports/build_master_md_WI-0120.log` + `reports/import_smoke_WI-0120.log`
- `reports/2026-01-31_WI-0120_db_move.md`
- `reports/2026-01-31_WI-0120_CLOSE.md`

### Allowlist
- `src/**/db/**` (solo area db) + `src/**/compat/**` (shims)
- `test/**` (solo se serve aggiornare import test)
- docs canonici consentiti: `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md` (solo se in allowlist tranche)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`

### Blocklist
- Move fuori area db

---

## WI-0130 — Refactor fisico tranche 2: core

**Status:** CLOSED (gates PASS — pytest 57 passed, 9 warnings; DeprecationWarning atteso: shims `src.core.*` → `src.phase0.core.*`)

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
- `test/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area core

---

## WI-0140 — Refactor fisico tranche 3: dataops

**Status:** CLOSED (gates PASS — pytest PASS; DeprecationWarning atteso: shims `src.dataops.*` → `src.phase0.dataops.*`)

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
- `test/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area dataops/ingest

---

## WI-0150 — Refactor fisico tranche 4: tools


**Status:** CLOSED (gates PASS — pytest PASS; DeprecationWarning atteso: shims `src.tools.*` → `src.phase0.tools.*`)
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
- `test/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area tools

---

## WI-0160 — Refactor fisico tranche 5: pages

**Status:** CLOSED (gates PASS — pytest PASS; DeprecationWarning atteso: shims pages legacy)

### DoD
- Move fisico area pages secondo Move Map (package `src/**/pages/**` o root `pages/**`).
- Import shims attivi.
- `pytest -q` PASS.

### Gate
- G0 + G1 + G2 + G3

### Evidence
- `reports/pytest_WI-0160.log` + `reports/guardian_lint_WI-0160.log` + `reports/build_master_md_WI-0160.log` + `reports/import_smoke_WI-0160.log`
- `reports/2026-02-02_WI-0160_pages_move.md`

- `reports/2026-02-02_WI-0160_CLOSE.md`
### Allowlist
- `src/**/pages/**` e/o `pages/**` (solo area pages) + `src/**/compat/**` (shims)
- `test/**` (solo se serve aggiornare import test)
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/**`
- docs canonici (solo se necessario): `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Blocklist
- Move fuori area pages

---

## WI-0170 — Tooling: WI Log Collector (B)

**Status:** CLOSED (gates PASS)

### Scopo
Creare un meccanismo stabile (1 comando) per controllare i log di un WI in `reports/`.

Requisiti:
- Modalità `normal`: attesi **7** log.
- Modalità `close`: attesi **4** log.
- Output per log: `OK` / `MISSING` / `EMPTY` + `HITS(n)` con linee (e numero riga).
- Collector "B" (Python), invocabile in PowerShell (nessuna funzione PS).
- Ogni run può scrivere un log del collector in `reports/`.

### Deliverable
- Nuovo comando:
  - `py scripts/guardian.py collect --wi WI-XXXX --mode {normal|close}`

### Allowlist
- `scripts/guardian.py`
- `scripts/wi_log_collector.py`
- `test/test_wi_log_collector.py`
- `.doc/TODO.md`
- `.doc/CURRENT_STATE.md`
- `.doc/LOGBOOK.md`
- `reports/2026-02-02_WI-0170_COLLECTOR.md`

### Blocklist
- `src/**`
- `docs/**`

### DoD
- `guardian collect` disponibile e stabile.
- Supporto UTF-16 (Out-File) nei log.
- `pytest` PASS (aggiunta unit test).
- Evidenza presente in `reports/`.

### Gate (da eseguire su target machine)
- `py -m pytest -q`

### Evidence
- `reports/2026-02-02_WI-0170_COLLECTOR.md`

---

## WI-0180 — Deprecation cleanup tranche A: callers `src.core.*` → `src.phase0.core.*`

**Status:** OPEN (phase2)

### Scopo
Eliminare l'uso interno dei legacy shims `src.core.*` aggiornando i call sites a importare direttamente da `src.phase0.core.*`.

### Deliverable
- Aggiornati import in `src/**` e `test/**` da `src.core.*` a `src.phase0.core.*`.
- Nuovo test di regressione: vieta import legacy da `src.core` fuori da `src/core/**`.
- Update doc: `mkdocs/docs/api/audit.md` punta a `src.phase0.core.audit_engine`.
- Evidenza: `reports/2026-02-02_WI-0180_DEPREC_CORE_CALLERS.md`.

### Allowlist
- `src/**` (solo file caller che importavano `src.core.*`)
- `test/**`
- `mkdocs/docs/api/audit.md`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-02_WI-0180_DEPREC_CORE_CALLERS.md`

### Blocklist
- rimozione shims `src/core/**` (resta per compat)
- refactor/move fuori scope

### DoD
- `pytest -q` PASS.
- Nessun `from|import src.core` fuori da `src/core/**` (enforced).
- DeprecationWarning da `src.core.*` non più generabile dai call sites.

### Gate
- `py -m pytest -q`
- (opzionale) `py scripts/guardian.py collect --wi WI-0180 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

### Evidence
- `reports/2026-02-02_WI-0180_DEPREC_CORE_CALLERS.md`


---

## WI-0190 — Deprecation cleanup tranche B: test imports `src.(db|tools|dataops)` → `src.phase0.*` + pages import

**Status:** CLOSED (phase2; gates PASS)

### Scopo
Ridurre/azzerare le DeprecationWarning provenienti dai test aggiornando gli import legacy che passano dagli shim.

### Deliverable
- Aggiornati import in `test/**`:
  - `src.db.*` → `src.phase0.db.*`
  - `src.tools.*` → `src.phase0.tools.*`
  - `src.dataops.*` → `src.phase0.dataops.*`
- Aggiornato import pagina Streamlit in test: `pages.06_Forecasts_Ranking` → `src.phase2.pages.06_Forecasts_Ranking`.
- Evidenza: `reports/2026-02-02_WI-0190_DEPREC_TEST_IMPORTS.md`.

### Allowlist
- `test/**`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-02_WI-0190_DEPREC_TEST_IMPORTS.md`

### Blocklist
- `src/**`
- rimozione shims

### DoD
- `pytest -q` PASS.
- `guardian collect --pattern DeprecationWarning` riduce/azzera hits lato test.

### Gate
- `py -m pytest -q`
- `py scripts/guardian.py collect --wi WI-0190 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

### Evidence
- `reports/2026-02-02_WI-0190_DEPREC_TEST_IMPORTS.md`


---

## WI-0200 — Deprecation cleanup tranche C: internal imports `src.db.*` → `src.phase0.db.*`

**Status:** CLOSED (gates PASS; residual warnings handled in WI-0210)

### Scopo
Eliminare le ultime `DeprecationWarning` provenienti dal codice runtime aggiornando gli import interni che passano dagli shim `src.db.*`.

### Deliverable
- Aggiornati import:
  - `src/phase0/core/audit_engine.py`: `src.db.migrate` → `src.phase0.db.migrate`
  - `src/intelligence_engine.py`: `src.db.audit_store` → `src.phase0.db.audit_store`
- Evidenza: `reports/2026-02-02_WI-0200_DEPREC_PHASE0_DB_IMPORTS.md`.

### Allowlist
- `src/phase0/core/audit_engine.py`
- `src/intelligence_engine.py`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-02_WI-0200_DEPREC_PHASE0_DB_IMPORTS.md`

### Blocklist
- rimozione shims `src/db/**` (resta per compat)
- refactor/move fuori scope

### DoD
- `pytest -q` PASS.
- `guardian collect --pattern DeprecationWarning` non mostra più hit per `src.db.*` dai call sites runtime.

### Gate
- `py -m pytest -q`
- `py scripts/guardian.py collect --wi WI-0200 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

### Evidence
- `reports/2026-02-02_WI-0200_DEPREC_PHASE0_DB_IMPORTS.md`
---

## WI-0210 — Deprecation cleanup tranche D: runtime imports in ranking + sentinel

**Status:** CLOSED (gates PASS; residual warnings moved to WI-0220)

### Scopo
Eliminare le `DeprecationWarning` residue emerse dai test (`pytest -q`) migrateando gli import runtime che passano ancora dagli shim `src.db.*` in moduli ad alto utilizzo.

### Deliverable
- Aggiornati import:
  - `src/forecast/ranking.py`: `src.db.audit_store` → `src.phase0.db.audit_store`
  - `src/sentinel_alpha.py`: `src.db.migrate` → `src.phase0.db.migrate`
- Evidenza: `reports/2026-02-02_WI-0210_DEPREC_RUNTIME_IMPORTS_D.md`.

### Allowlist
- `src/forecast/ranking.py`
- `src/sentinel_alpha.py`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-02_WI-0210_DEPREC_RUNTIME_IMPORTS_D.md`

### Blocklist
- rimozione shims `src/db/**` (resta per compat)
- refactor/move fuori scope

### DoD
- `pytest -q` PASS.
- `guardian collect --pattern DeprecationWarning` non mostra più hit per:
  - `src/forecast/ranking.py` (audit_store)
  - `src/sentinel_alpha.py` (migrate)

### Gate
- `py -m pytest -q`
- `py scripts/guardian.py collect --wi WI-0210 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

### Evidence
- `reports/2026-02-02_WI-0210_DEPREC_RUNTIME_IMPORTS_D.md`


---

## WI-0220 — Deprecation cleanup tranche E: verify_ticker_mappings `src.db.*` → `src.phase0.db.*`

**Status:** CLOSED (gates PASS)

### Scopo
Rimuovere le `DeprecationWarning` residue provenienti da `src/phase0/tools/verify_ticker_mappings.py` aggiornando l'ultimo import legacy che passa dagli shim `src.db.*`.

### Deliverable
- Aggiornato import:
  - `src/phase0/tools/verify_ticker_mappings.py`: `src.db.migrate` → `src.phase0.db.migrate`
- Evidenza: `reports/2026-02-02_WI-0220_DEPREC_VERIFY_TICKER_MAPPINGS.md`.

### Allowlist
- `src/phase0/tools/verify_ticker_mappings.py`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-02_WI-0220_DEPREC_VERIFY_TICKER_MAPPINGS.md`

### Blocklist
- rimozione shims `src/db/**` (resta per compat)
- refactor/move fuori scope

### DoD
- `pytest -q` PASS.
- `guardian collect --pattern DeprecationWarning` non mostra più hit per `src.db.*` provenienti da `verify_ticker_mappings`.

### Gate
- `py -m pytest -q`
- `py scripts/guardian.py collect --wi WI-0220 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

### Evidence
- `reports/2026-02-02_WI-0220_DEPREC_VERIFY_TICKER_MAPPINGS.md`


---

## WI-0230 — Deprecation cleanup tranche F: UI + entrypoints `src.db|src.tools|src.dataops` → `src.phase0.*`

**Status:** CLOSED (gates PASS; strict DeprecationWarning gate PASS)

### Scopo
Eliminare import legacy che passano dagli shim da:
- entrypoints/runtime: `app.py`, `main.py`, `scripts/execute.py`, `src/morning_bulletin.py`, `src/monitoring/__main__.py`, `src/intelligence_engine.py`
- UI pages: `src/phase2/pages/*` (gates/audit/trades/datagaps/execution/tca/dataops)

### Deliverable
- Aggiornati import:
  - `src.db.*` → `src.phase0.db.*`
  - `src.tools.*` → `src.phase0.tools.*`
  - `src.dataops.*` → `src.phase0.dataops.*`
- Evidenza: `reports/2026-02-02_WI-0230_DEPREC_UI_ENTRYPOINTS.md`.

### Allowlist
- `app.py`
- `main.py`
- `scripts/execute.py`
- `src/morning_bulletin.py`
- `src/monitoring/__main__.py`
- `src/intelligence_engine.py`
- `src/phase2/pages/02_Gates_Data_Quality.py`
- `src/phase2/pages/03_Audit_Runs.py`
- `src/phase2/pages/04_Trades_Equity.py`
- `src/phase2/pages/05_Data_Gaps_Backfill.py`
- `src/phase2/pages/09_Execution_Log.py`
- `src/phase2/pages/10_Monitoring_TCA.py`
- `src/phase2/pages/11_DataOps_Control_Room.py`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-02_WI-0230_DEPREC_UI_ENTRYPOINTS.md`

### Blocklist
- rimozione shims `src/db/**`, `src/tools/**`, `src/dataops/**` (restano per compat)
- refactor/move fuori scope

### DoD
- `pytest -q` PASS.
- `guardian collect --pattern DeprecationWarning` non mostra hit per `src.db|src.tools|src.dataops` provenienti dai file in allowlist.

### Gate
- `py -m pytest -q -W error::DeprecationWarning`
- `py scripts/guardian.py collect --wi WI-0230 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

### Evidence
- `reports/2026-02-02_WI-0230_DEPREC_UI_ENTRYPOINTS.md`


---

## WI-0240 — Tooling: one-command WI gate runner (B) + doc alignment

**Status:** CLOSED (phase2)

### Scopo
Consolidare un meccanismo stabile “1 comando” per eseguire e verificare la gate suite di un WI:
- scrive i log attesi in `reports/` (normal: 7 log; close: 4 log)
- integra `collector B` per check presence/emptiness + pattern hits
- default: `pytest` con gate strict `DeprecationWarning` (warning → error)

### Deliverable
- Nuovo runner: `py scripts/guardian.py gate --wi WI-XXXX --mode normal|close`
- Docset aggiornato con riferimenti (PDD/Evidence/Traceability/Module Registry)
- Unit test (dry-run) per garantire naming e log non-vuoti
- Evidenza: `reports/2026-02-03_WI-0240_GATE_RUNNER.md`
- `reports/2026-02-03_WI-0240_CLOSE.md`

### Allowlist
- `scripts/guardian.py`
- `scripts/wi_gate_runner.py`
- `docs/003_PDD_OBSERVER.md`
- `docs/005_TRACEABILITY_MATRIX.md`
- `docs/008_EVIDENCE_PACK.md`
- `docs/010_MODULE_REGISTRY.md`
- `.doc/_GUARDIAN/_GUARDIAN_workflow.md`
- `test/test_wi_gate_runner.py`
- `.doc/TODO.md`, `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
- `reports/2026-02-03_WI-0240_GATE_RUNNER.md`
- `.doc/CANONICAL_LIBRARY.md`
- `.doc/canonical/derived/DDT.md`
- `.doc/canonical/derived/PROJ.md`
- `.doc/canonical/derived/TECH.md`
- `reports/2026-02-03_WI-0240_CLOSE.md`

### Blocklist
- Nessun refactor fisico in blocco
- Nessuna modifica a `src/**` (fuori scope)

### DoD
- `py scripts/guardian.py gate --wi WI-0240 --mode normal` crea tutti i log attesi e termina con exit code 0 se PASS.
- `py scripts/guardian.py gate --wi WI-0240 --mode close` crea 4 log `_CLOSE` e termina con exit code 0 se PASS.
- `py -m pytest -q -W error::DeprecationWarning` PASS (61 passed atteso nello snapshot corrente).
- Collector B su WI-0240: HITS(0) su tutti i log (normal + close).
- Documentazione aggiornata: cross-reference coerenti (PDD/Evidence/Traceability/Module Registry).

### Gate
- `py scripts/guardian.py gate --wi WI-0240 --mode normal --write-collect-log`
- `py -m pytest -q -W error::DeprecationWarning`

### Evidence
- `reports/2026-02-03_WI-0240_GATE_RUNNER.md`
- `reports/2026-02-03_WI-0240_CLOSE.md`


## WI-0260 — Tooling: Collector strict-hits + profiles (B)

**Status:** CLOSED (2026-02-03)

### Goal
- Stabilizzare il collector (B) come gate: `HITS` può diventare *bloccante* (`--fail-on-hits`).
- Profili: `hardfail|deprec|none`.
- Anti-false-positive: ignorare righe runner `CMD:` / `DRY-RUN:`.

### Allowlist
- `scripts/wi_log_collector.py`
- `scripts/wi_gate_runner.py`
- `scripts/guardian.py`
- `tests/test_wi_log_collector.py`
- `tests/test_wi_gate_runner.py`
- Docs/canonici: `.doc/_GUARDIAN/_GUARDIAN_workflow.md`, `docs/003_PDD_OBSERVER.md`, `docs/008_EVIDENCE_PACK.md`, `docs/010_MODULE_REGISTRY.md`, `docs/005_TRACEABILITY_MATRIX.md`

### Gate
- `py scripts/guardian.py gate --wi WI-0260 --mode normal --write-collect-log`

### Evidence
- `reports/<gate>_WI-0260.log` (7)
- `reports/wi_collect_WI-0260.log`
- `reports/2026-02-03_WI-0260_COLLECTOR_STRICT.md`


## WI-0270 — Stabilizzazione EOL doc-tooling (CRLF/LF)

**Status:** CLOSED (2026-02-03)

### Goal
- Eliminare churn e warning Git “CRLF will be replaced by LF” su file doc/canonici generati da tooling (Windows).
- Rendere deterministico l’output EOL (`LF`) per:
  - `.doc/**` (sync/derive/next)
  - `docs/OBSERVER_v1.2.5.md` (build master)
  - mkdocs views generate (se usate)

### Allowlist
- `scripts/guardian_ops.py`
- `scripts/guardian_next.py`
- `scripts/build_master_md.py`
- `scripts/gen_mkdocs_views.py`
- `.doc/_GUARDIAN/_GUARDIAN_workflow.md`
- `docs/008_EVIDENCE_PACK.md`
- `.doc/TODO.md`
- `.doc/CURRENT_STATE.md`
- `.doc/LOGBOOK.md`
- `reports/2026-02-03_WI-0270_EOL_STABILIZE.md`

### Blocklist
- `src/**`
- `tests/**`
- `pages/**`

### Gate
- `py scripts/guardian.py gate --wi WI-0270 --mode normal --write-collect-log`

### Evidence
- `reports/<gate>_WI-0270.log` (7)
- `reports/wi_collect_WI-0270.log`
- `reports/2026-02-03_WI-0270_EOL_STABILIZE.md`


## WI-0280 — CI: GUARDIAN gate + reports artifact

**Status:** CLOSED (2026-02-03)

### Goal
- Allineare GitHub Actions ai gate locali (1 comando) usando `scripts/guardian.py gate`.
- Rendere CI *ripetibile* e verificabile via artifact `reports/`.
- Stabilizzare runner legacy `main_test.py` (puntare a `tests/`).

### Allowlist
- `.github/workflows/ci.yml`
- `main_test.py`
- `docs/008_EVIDENCE_PACK.md`
- `.doc/_GUARDIAN/_GUARDIAN_workflow.md`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`, `.doc/LOGBOOK.md`
- `reports/2026-02-03_WI-0280_CI_GATE_ALIGN.md`

### Gate
- `py scripts/guardian.py gate --wi WI-0280 --mode normal --write-collect-log`
- (CI) workflow: `python scripts/guardian.py gate --wi WI-0000 --mode normal --write-collect-log`

### Evidence
- `reports/<gate>_WI-0280.log` (7)
- `reports/wi_collect_WI-0280.log`
- `reports/2026-02-03_WI-0280_CI_GATE_ALIGN.md`

## WI-0290 — Docs integrity check (warn)

**Status:** CLOSED (2026-02-03)

### Goal
- Aggiungere un controllo offline di integrità doc (`Markdown` links + anchors) con output ripetibile.
- Integrare il check nel gate runner senza modificare il contratto Collector B (7/4 log).
- Default: **warn** (non blocca), pronta promozione a **hard** in WI successivo.

### Allowlist
- `scripts/doc_integrity_check.py` (NEW)
- `scripts/guardian.py`
- `scripts/wi_gate_runner.py`
- `tests/test_wi_gate_runner.py`
- `tests/test_doc_integrity_check.py` (NEW)
- `.doc/_GUARDIAN/_GUARDIAN_workflow.md`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`, `.doc/LOGBOOK.md`
- `docs/003_PDD_OBSERVER.md`
- `docs/005_TRACEABILITY_MATRIX.md`
- `docs/008_EVIDENCE_PACK.md`
- `docs/010_MODULE_REGISTRY.md`
- `docs/OBSERVER_v1.2.5.md`
- `reports/2026-02-03_WI-0290_DOCS_CHECK_WARN.md`

### Gate
- `py scripts/guardian.py gate --wi WI-0290 --mode normal --write-collect-log`
- (docs-only) `py scripts/guardian.py docs-check --mode warn`

### Expected logs
- Standard 7/4 WI logs + meta/collect logs
- Extra (non-Collector): `reports/docs_check_WI-0290[_CLOSE].log`

### Evidence
- `reports/2026-02-03_WI-0290_DOCS_CHECK_WARN.md`

## WI-0300 — Docs integrity check (hard)

**Goal:** promuovere `docs-check` da modalità `warn` a **gate hardfail** (exit != 0) nel gate runner.

**Allowlist:** scripts/doc_integrity_check.py, scripts/wi_gate_runner.py, scripts/guardian.py, docset (.doc/*, docs/*), reports/*.

**Gates:**
- `py scripts/guardian.py gate --wi WI-0300 --mode close --write-collect-log`
- `py scripts/guardian.py gate --wi WI-0300 --mode normal --write-collect-log`

**Evidence:** `reports/2026-02-03_WI-0300_DOCS_CHECK_HARD.md`

Status: **CLOSED**
