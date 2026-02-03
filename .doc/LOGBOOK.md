# LOGBOOK — OBSERVER

## 2026-01-30 — WI-0107 (Refactor Plan, virtual) — planning milestone
- Gates executed: PASS (pytest/guardian/build_master) — logs: reports/*_WI-0107.log

### Outcome
- Pianificazione granulare completata (milestone 1): **nessun refactor fisico** e **nessun move in `src/`**.
- Preparata la transizione: WI-0104 (epic) → sotto-WI virtuali (0110..0115) → tranche fisiche (0120..0160).

### Canonici/asset introdotti
- `docs/012_REFACTOR_PLAN_VIRTUAL.md` (canonico)
- Aggiornati per includere il canonico:
  - `docs/000_README_DOCSET.md`
  - `scripts/build_master_md.py`

### Governance files
- `.doc/TODO.md` aggiornato con WI-0107 + sottowork + tranche fisiche placeholder.
- `.doc/CURRENT_STATE.md` creato come baseline.

### Evidence
- `reports/2026-01-30_WI-0107_planning.md`

### Gates executed (repo canonico)
- PASS — `py -m pytest`  → log: `reports/pytest_WI-0107.log`
- PASS — `py scripts/guardian.py lint` → log: `reports/guardian_lint_WI-0107.log`
- PASS — `py scripts/build_master_md.py` → log: `reports/build_master_md_WI-0107.log`

### Notes
- L’inputpack iniziale non conteneva `.doc/LOGBOOK.md` e `CURRENT_STATE/`; questi file sono stati creati **come file veri** per abilitare governance e audit trail.

## 2026-01-30 — WI-0110 (Inventory & boundary map, virtual) — DONE
- Gates executed: PASS (pytest/guardian) — logs: `reports/pytest_WI-0110.log`, `reports/guardian_lint_WI-0110.log`

### Outcome
- Generato inventory “as-built” e boundary map (euristica import roots + cross-area).
- Aggiornato `docs/012_REFACTOR_PLAN_VIRTUAL.md` con blocco auto WI-0110 (marker `<!-- WI-0110:BEGIN/END -->`).

### Evidence
- `reports/WI-0110_inventory.md`
- `reports/pytest_WI-0110.log`
- `reports/guardian_lint_WI-0110.log`

### Notes
- WI-0110 è **plan-only**: nessun move e nessuna modifica a `src/**` (rispettata blocklist).

## 2026-01-30 — WI-0111 (Move Map final, virtual) — DONE
- Gates executed: PASS (pytest/guardian) — logs: `reports/pytest_WI-0111.log`, `reports/guardian_lint_WI-0111.log`

### Outcome
- Move Map virtuale finalizzata per tranche 1..5 (db/core/dataops/tools/pages) + “shared candidates/PHASE0”.
- Canonico `docs/012_REFACTOR_PLAN_VIRTUAL.md` aggiornato con snapshot auto WI-0111.

### Evidence
- `reports/WI-0111_move_map.md`
- `reports/pytest_WI-0111.log`
- `reports/guardian_lint_WI-0111.log`

## 2026-01-30 — WI-0112 (Import shims plan + deprecation policy) — DONE
- Gates executed: PASS (pytest/guardian) — logs: `reports/pytest_WI-0112.log`, `reports/guardian_lint_WI-0112.log`

### Outcome
- Definita strategia shims (module/package) + policy di deprecazione misurabile e applicabile tranche-per-tranche.
- Aggiornato canonico `docs/012_REFACTOR_PLAN_VIRTUAL.md` con snapshot auto WI-0112.

### Evidence
- `reports/WI-0112_shims_policy.md`
- `reports/pytest_WI-0112.log`
- `reports/guardian_lint_WI-0112.log`

### Blocklist respected
- Nessun move/modifica in `src/**` e `test/**` (plan-only).

## 2026-01-30 — WI-0113 (Rollback plan, virtual) — DONE
- Gates executed: PASS (pytest/guardian) — logs: `reports/pytest_WI-0113.log`, `reports/guardian_lint_WI-0113.log`

### Outcome
- Protocollo di rollback per tranche fisiche (tag pre/post, reset vs revert) a supporto dei WI-0120..0160.

### Evidence
- `reports/WI-0113_rollback.md`
- `reports/pytest_WI-0113.log`
- `reports/guardian_lint_WI-0113.log`

### Blocklist
- `src/**`, `test/**` (no change)


## 2026-01-30 — WI-0114 (Gate protocol + expected logs, virtual) — DONE
- Gates executed: PASS (pytest/guardian) — logs: `reports/pytest_WI-0114.log`, `reports/guardian_lint_WI-0114.log`

### Outcome
- Standardizzata la gate suite (G0..G3) e il naming log per allineare doc canonici + pratica operativa.

### Evidence
- `reports/WI-0114_gates.md`
- `reports/pytest_WI-0114.log`
- `reports/guardian_lint_WI-0114.log`

### Blocklist
- `src/**`, `test/**` (no change)

## 2026-01-30 — WI-0115 (Skeleton tranche fisiche, TODO-only) — DONE
- Gates executed: PASS (pytest/guardian) — logs: `reports/pytest_WI-0115.log`, `reports/guardian_lint_WI-0115.log`

### Outcome
- Inserite tranche fisiche WI-0120..0160 come skeleton coerenti (DoD/Gate/Evidence/Allowlist/Blocklist) in `.doc/TODO.md`.
- Nessuna modifica a `src/**`, `test/**`, `docs/**` (plan-only).

### Evidence
- `.doc/TODO.md` — sezione WI-0115 + tranche WI-0120..0160
- `reports/pytest_WI-0115.log`
- `reports/guardian_lint_WI-0115.log`

### Blocklist
- `src/**`, `test/**`, `docs/**` (no change)

## 2026-01-31 — WI-0120 (Refactor fisico tranche 1: db) — CLOSED (gates PASS)

### Outcome
- Eseguito move fisico area `db` secondo Move Map:
  - `src/db/**` → `src/phase0/db/**`
- Introdotti import shims per preservare compatibilità:
  - `src/db/*` reindirizza a `src/phase0/db/*` con `DeprecationWarning`
  - entrypoint preservato: `py -m src.db.migrate`
- Introdotto compat layer:
  - `src/compat/shims.py`

### Canonici aggiornati (allowlist tranche)
- `docs/010_MODULE_REGISTRY.md`
- `docs/005_TRACEABILITY_MATRIX.md`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`

### Evidence
- `reports/2026-01-31_WI-0120_db_move.md`
- `reports/2026-01-31_WI-0120_CLOSE.md`

### Gates (esito su target machine)

- `guardian lint`: PASS
- `compileall -q`: PASS (nessun output, atteso)
- import smoke: PASS (`OK`)
- `pytest -q`: PASS — `57 passed, 3 warnings` (DeprecationWarning atteso: shims `src.db.*` → `src.phase0.db.*`)
- `guardian sync --clean`: PASS (sync completato, direct mode)
- `guardian derive`: PASS
- `build_master_md`: PASS



## 2026-01-31 — WI-0130 (Refactor fisico tranche 2: core) — CLOSED (gates PASS)

### Outcome
- Eseguito move fisico area `core` secondo Move Map:
  - `src/core/**` → `src/phase0/core/**`
- Introdotti import shims per preservare compatibilità:
  - `src/core/*` reindirizza a `src/phase0/core/*` con `DeprecationWarning`
- Migliorata igiene import interni core (relative imports) per evitare dipendenza dai legacy shims.

### Canonici aggiornati (allowlist tranche)
- `docs/010_MODULE_REGISTRY.md`
- `docs/005_TRACEABILITY_MATRIX.md`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`

### Evidence
- `reports/2026-01-31_WI-0130_core_move.md`
- `reports/2026-01-31_WI-0130_CLOSE.md`

### Gates (esito su target machine)
- `guardian lint`: PASS
- `compileall -q`: PASS (nessun output, atteso)
- import smoke: PASS (`OK`)
- `pytest -q`: PASS — `57 passed, 9 warnings` (DeprecationWarning atteso: shims `src.core.*` → `src.phase0.core.*`)
- `guardian sync --clean`: PASS (sync completato, direct mode; fingerprint `aa566c3a4d5a83c4`)
- `guardian derive`: PASS
- `build_master_md`: PASS


## 2026-02-01 — WI-0140 (Refactor fisico tranche 3: dataops) — CLOSED (gates PASS)

### Outcome
- Eseguito move fisico area `dataops` secondo Move Map:
  - `src/dataops/**` → `src/phase0/dataops/**`
- Introdotti import shims per preservare compatibilità:
  - `src/dataops/*` reindirizza a `src/phase0/dataops/*` con `DeprecationWarning`

### Canonici aggiornati (allowlist tranche)
- `docs/010_MODULE_REGISTRY.md`
- `docs/005_TRACEABILITY_MATRIX.md`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`

### Evidence
- `reports/2026-02-01_WI-0140_dataops_move.md`
- `reports/2026-02-01_WI-0140_CLOSE.md`

### Gates (esito su target machine)
- `guardian lint`: PASS
- `compileall -q`: PASS (nessun output, atteso)
- import smoke: PASS (`OK`)
- `pytest -q`: PASS (DeprecationWarning atteso: shims `src.dataops.*` → `src.phase0.dataops.*`)
- `guardian sync --clean`: PASS (sync completato, direct mode; fingerprint: vedi log `reports/guardian_sync_WI-0140.log`)
- `guardian derive`: PASS
- `build_master_md`: PASS

## 2026-02-01 — WI-0150 (Refactor fisico tranche 4: tools) — CLOSED (gates PASS)

### Outcome
- Eseguito move fisico area `tools` secondo Move Map:
  - `src/tools/**` → `src/phase0/tools/**`
- Introdotti import shims per preservare compatibilità:
  - `src/tools/*` reindirizza a `src/phase0/tools/*` con `DeprecationWarning`

### Canonici aggiornati (allowlist tranche)
- `docs/010_MODULE_REGISTRY.md`
- `docs/005_TRACEABILITY_MATRIX.md`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`

### Evidence
- `reports/2026-02-01_WI-0150_tools_move.md`
- `reports/2026-02-01_WI-0150_CLOSE.md`

### Gates (esito su target machine)
- `guardian lint`: PASS
- `compileall -q`: PASS (nessun output, atteso)
- import smoke: PASS (`OK`)
- `pytest -q`: PASS (DeprecationWarning atteso: shims `src.tools.*` → `src.phase0.tools.*`)
- `guardian sync --clean`: PASS (sync completato, direct mode; fingerprint: vedi log `reports/guardian_sync_WI-0150.log`)
- `guardian derive`: PASS
- `build_master_md`: PASS

## 2026-02-02 — WI-0160 (Refactor fisico tranche 5: pages) — CLOSED (gates PASS)

### Outcome
- Eseguito move fisico area `pages` secondo Move Map:
  - `pages/**` → `src/phase2/pages/**` (implementazione reale)
- Introdotti shims legacy per preservare compatibilità:
  - wrapper in `pages/*.py` verso `src/phase2/pages/*` con `DeprecationWarning`

### Evidence
- `reports/2026-02-02_WI-0160_pages_move.md`
- `reports/2026-02-02_WI-0160_CLOSE.md`

### Gates (esito su target machine)
- `guardian lint`: PASS
- `compileall -q`: PASS (nessun output, atteso)
- import smoke: PASS (`OK`)
- `pytest -q`: PASS (DeprecationWarning atteso: import legacy `pages.*` / `src.pages.*`)
- `guardian sync --clean`: PASS (sync completato, direct mode; fingerprint: vedi log `reports/guardian_sync_WI-0160.log`)
- `guardian derive`: PASS
- `build_master_md`: PASS



## 2026-02-02 — WI-0170 (Tooling: WI Log Collector B) — CLOSED (gates PASS)

### Outcome (intended)
- Introdotto comando `guardian collect` (collector B, Python) per verificare la presenza/coerenza dei log di un WI in `reports/`.
- Modalità:
  - `normal`: 7 log attesi
  - `close`: 4 log attesi
- Output per file: `OK` / `MISSING` / `EMPTY` + `HITS(n)` con linee (e numero riga).

### Allowlist
- `scripts/guardian.py`
- `scripts/wi_log_collector.py`
- `test/test_wi_log_collector.py`
- `.doc/TODO.md`, `.doc/CURRENT_STATE.md`, `.doc/LOGBOOK.md`
- `reports/2026-02-02_WI-0170_COLLECTOR.md`

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0170_COLLECTOR.md`

## 2026-02-02 — WI-0180 (Deprecation cleanup tranche A: src.core callers) — OPEN

### Outcome (intended)
- Migrazione import nei call sites: `src.core.*` → `src.phase0.core.*`.
- Aggiunto test regressione: vieta import legacy `src.core` fuori da `src/core/**`.
- Aggiornato mkdocs API (audit) su modulo canonical.

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0180_DEPREC_CORE_CALLERS.md`

### Gates (da eseguire su target machine)
- `guardian lint`
- `compileall -q`
- import smoke
- `pytest -q`
- `guardian sync --clean`
- `guardian derive`
- `build_master_md`
- `guardian collect --wi WI-0180 --mode normal --write-log --pattern DeprecationWarning --pattern \"\[DEPRECATED\]\"`


## 2026-02-02 — WI-0190 (Deprecation cleanup tranche B: test imports + pages import) — CLOSED (gates PASS)

### Outcome (intended)
- Aggiornare gli import nei test che passano dagli shim legacy:
  - `src.db.*` → `src.phase0.db.*`
  - `src.tools.*` → `src.phase0.tools.*`
  - `src.dataops.*` → `src.phase0.dataops.*`
- Aggiornare test import pagina Streamlit: `pages.06_Forecasts_Ranking` → `src.phase2.pages.06_Forecasts_Ranking`.

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0190_DEPREC_TEST_IMPORTS.md`

### Gates (da eseguire su target machine)
- `guardian lint`
- `compileall -q`
- import smoke
- `pytest -q`
- `guardian sync --clean`
- `guardian derive`
- `build_master_md`
- `guardian collect --wi WI-0190 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`


## 2026-02-02 — WI-0200 (Deprecation cleanup tranche C: internal src.db imports) — CLOSED (scope met; residual warnings moved to WI-0210)

### Outcome (intended)
- Eliminare le ultime DeprecationWarning provenienti dai call sites runtime aggiornando gli import:
  - `src/phase0/core/audit_engine.py`: `src.db.migrate` → `src.phase0.db.migrate`
  - `src/intelligence_engine.py`: `src.db.audit_store` → `src.phase0.db.audit_store`

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0200_DEPREC_PHASE0_DB_IMPORTS.md`

### Gates (da eseguire su target machine)
- `guardian lint`
- `compileall -q`
- import smoke
- `pytest -q`
- `guardian sync --clean`
- `guardian derive`
- `build_master_md`
- `guardian collect --wi WI-0200 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`

## 2026-02-02 — WI-0210 (Deprecation cleanup tranche D: runtime imports ranking+sentinel) — CLOSED (gates PASS; residual warnings moved to WI-0220)

### Outcome (intended)
- Eliminare le DeprecationWarning residue emerse in `pytest -q` aggiornando import runtime:
  - `src/forecast/ranking.py`: `src.db.audit_store` → `src.phase0.db.audit_store`
  - `src/sentinel_alpha.py`: `src.db.migrate` → `src.phase0.db.migrate`

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0210_DEPREC_RUNTIME_IMPORTS_D.md`

### Gates (da eseguire su target machine)
- `guardian lint`
- `compileall -q`
- import smoke
- `pytest -q`
- `guardian sync --clean`
- `guardian derive`
- `build_master_md`
- `guardian collect --wi WI-0210 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`


## 2026-02-02 — WI-0220 (Deprecation cleanup tranche E: verify_ticker_mappings imports) — CLOSED (gates PASS)

### Outcome (intended)
- Rimuovere le DeprecationWarning residue provenienti da `src/phase0/tools/verify_ticker_mappings.py` aggiornando l'import legacy:
  - `src.db.migrate` → `src.phase0.db.migrate`

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0220_DEPREC_VERIFY_TICKER_MAPPINGS.md`

### Gates (da eseguire su target machine)
- `guardian lint`
- `compileall -q`
- import smoke
- `pytest -q`
- `guardian sync --clean`
- `guardian derive`
- `build_master_md`
- `guardian collect --wi WI-0220 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`


## 2026-02-02 — WI-0230 (Deprecation cleanup tranche F: UI + entrypoints imports) — CLOSED (gates PASS; strict DeprecationWarning gate PASS)

### Outcome (intended)
- Eliminare import legacy che passano dagli shim (evitare `DeprecationWarning`) in:
  - entrypoints/runtime: `app.py`, `main.py`, `scripts/execute.py`, `src/morning_bulletin.py`, `src/monitoring/__main__.py`, `src/intelligence_engine.py`
  - UI pages: `src/phase2/pages/*` (gates/audit/trades/datagaps/execution/tca/dataops)

### Evidence (da produrre su target machine)
- `reports/2026-02-02_WI-0230_DEPREC_UI_ENTRYPOINTS.md`

### Gates (da eseguire su target machine)
- `guardian lint`
- `compileall -q`
- import smoke
- `pytest -q -W error::DeprecationWarning`
- `guardian sync --clean`
- `guardian derive`
- `build_master_md`
- `guardian collect --wi WI-0230 --mode normal --write-log --pattern DeprecationWarning --pattern "\[DEPRECATED\]"`


## 2026-02-03 — WI-0240 (Tooling: one-command WI gate runner B + doc alignment) — CLOSED

### Outcome (intended)
- Consolidare un comando unico per eseguire i gate per WI con logging standardizzato in `reports/`.
- Integrare il Collector (B) per verificare: presence/emptiness + pattern hits.
- Aggiornare la documentazione canonica (PDD/Evidence/Traceability/Module Registry) con cross reference coerenti.

### Evidence
- `reports/2026-02-03_WI-0240_GATE_RUNNER.md`
- `reports/2026-02-03_WI-0240_CLOSE.md`

### Gates (eseguiti su target machine)
- `py scripts/guardian.py gate --wi WI-0240 --mode normal --write-collect-log`
- `py scripts/guardian.py gate --wi WI-0240 --mode close --write-collect-log`
- `py -m pytest -q -W error::DeprecationWarning`

### Outcome (actual)
- Gate runner PASS in modalità normal (7 log) e close (4 log).
- Collector B: HITS(0) su tutti i log WI-0240 (normal + close).
- Strict gate: `pytest -W error::DeprecationWarning` PASS.


## 2026-02-03 — WI-0260

- Tooling: Collector B profiles + strict-hits default in gate runner.
- Goal: stabilizzare segnali hard-fail nei log (no falsi positivi su CMD/DRY-RUN).
