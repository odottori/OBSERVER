---
doc_id: 012_REFACTOR_PLAN_VIRTUAL
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-30
---
# Refactor Plan (virtual) — pre-WI-0104

## Scopo

Questo documento definisce **la fase intermedia obbligatoria** prima del refactor fisico (WI-0104), con obiettivi:

1. Formalizzare una **Move Map** (*virtual refactor*): mappa *as-is → to-be* per package (db/core/dataops/tools/pages) e per fase (PHASE0/PHASE1/PHASE2/UI).
2. Definire una strategia di **import shims** (compatibilità) + una **deprecation policy** verificabile.
3. Introdurre un protocollo di lavoro **a tranche** (1 tranche = 1 WI) con **gates ripetibili** e output di evidenza.
4. Definire un **rollback plan** per ridurre il rischio operativo durante gli spostamenti fisici.

## Non-goals (espliciti)

- Nessuno spostamento di file in `src/` in questa milestone (solo pianificazione).
- Nessuna riorganizzazione “in blocco”: WI-0104 viene trattato come *epic* esploso in tranche.
- Nessun cambiamento funzionale (comportamento runtime, schema DB, output UI): il refactor fisico è progettato per essere *behavior-preserving*.

## Vincoli operativi

- Il refactor fisico avviene **solo per tranche**, con `pytest` sempre PASS.
- Dopo ogni tranche si producono log ripetibili in `reports/` (pytest + gate suite) e si aggiornano i canonici **solo se** in allowlist.
- La compatibilità di import verso l’esterno è mantenuta tramite shims per una finestra di deprecazione definita.

## Definizioni

- **Virtual refactor**: documentazione e pianificazione della nuova topologia (Move Map) senza movimenti fisici.
- **Tranche**: insieme minimo di move/rename coerenti, confinato ad un package (es. `db`) e consegnato come 1 WI.
- **Gate**: insieme di controlli ripetibili (comandi) che devono PASSARE per considerare chiuso un WI.
- **Import shim**: modulo o package “stub” che reindirizza un vecchio import al nuovo path (con warning di deprecazione).

## Assunzioni e rischio

- Questo piano assume l’esistenza (logica) delle aree `db/`, `core/`, `dataops/`, `tools/`, `pages/` nel codice (come da backlog).
- I path esatti possono differire (es. `src/observer/...` vs `src/app/...`). La Move Map usa quindi **pattern** e non path assoluti.
- Il rischio primario non è tecnico ma di **drift**: per mitigarlo, le tranche sono piccole e con gates ripetibili.

## Target structure (to-be) — concettuale

> Nota: la struttura to-be è un target logico; i path precisi si finalizzano nella WI-0110 (inventory).

```text
src/<pkg_root>/
  phase0/                 # infrastruttura: config, logging, db access, utils
  phase1/                 # data pipeline + dataops
  phase2/                 # UI / pages / orchestration / signals
  compat/                 # import shims (solo durante la finestra di deprecazione)
```

### Regole di assegnazione per fase (heuristic)

- **PHASE0**: runtime base, config, logging, error model, DB access layer, path utilities.
- **PHASE1**: ingestion, dataops, dq, sentinel runner, batch jobs.
- **PHASE2/UI**: streamlit pages, orchestration UI, view-model, helpers UI, features “presentational”.

## Gate toolkit (ripetibile)

### Gate G0 — Baseline (no-op)
Obiettivo: confermare che il repo è in stato pulito e riproducibile prima di una tranche.

- `py -m pytest` (nessuna modifica attesa, deve PASSARE)
- `py scripts/guardian.py lint` (strutturale)

Output atteso (per tranche):
- `reports/pytest_tranche_<WI>.log`
- `reports/guardian_lint_<WI>.log`

### Gate G1 — Import smoke
Obiettivo: intercettare rotture d’import prima di eseguire test completi.

- `py -c "import <pkg_root>; print('OK')"`
- (opzionale) `py -m compileall -q src`

Output atteso:
- `reports/import_smoke_<WI>.log`
- `reports/compileall_<WI>.log`

### Gate G2 — Pytest
Obiettivo: regressione funzionale.

- `py -m pytest -q`

Output atteso:
- `reports/pytest_tranche_<WI>.log`

### Gate G3 — Docset/derived sync
Obiettivo: evitare drift tra canonici e derivati.

- `py scripts/guardian.py sync --clean`
- `py scripts/guardian.py derive`
- `py scripts/build_master_md.py`

Output atteso:
- `reports/guardian_sync_<WI>.log`
- `reports/guardian_derive_<WI>.log`
- `reports/build_master_md_<WI>.log`

## Move Map (virtual) — tranche per package

### Tranche 1 — db

| Area | As-is (pattern) | To-be (target) | Fase | Note |
|---|---|---|---|---|
| DB access layer | `src/**/db/**` | `src/<pkg_root>/phase0/db/**` | PHASE0 | connessione, query helpers, schema access |
| Schema artifacts | `src/**/db/schema*` | `src/<pkg_root>/phase0/db/schema*` | PHASE0 | se presenti in python; assets esterni restano fuori |

### Tranche 2 — core

| Area | As-is (pattern) | To-be (target) | Fase | Note |
|---|---|---|---|---|
| Core runtime | `src/**/core/**` | `src/<pkg_root>/phase0/core/**` | PHASE0 | config, logging, error model, path utils |
| Shared utilities | `src/**/utils/**` | `src/<pkg_root>/phase0/utils/**` | PHASE0 | utilities senza dipendenze PHASE1/2 |

### Tranche 3 — dataops

| Area | As-is (pattern) | To-be (target) | Fase | Note |
|---|---|---|---|---|
| DataOps jobs | `src/**/dataops/**` | `src/<pkg_root>/phase1/dataops/**` | PHASE1 | dq runs, metrics, job orchestration |
| Ingestion | `src/**/ingest/**` | `src/<pkg_root>/phase1/ingest/**` | PHASE1 | load, normalize, snapshot |

### Tranche 4 — tools

| Area | As-is (pattern) | To-be (target) | Fase | Note |
|---|---|---|---|---|
| CLI/tools | `src/**/tools/**` | `src/<pkg_root>/phase2/tools/**` | PHASE2 | comandi UI/dev; se batch PHASE1, ricollocare |

### Tranche 5 — pages

| Area | As-is (pattern) | To-be (target) | Fase | Note |
|---|---|---|---|---|
| Streamlit pages | `src/**/pages/**` oppure `pages/**` | `src/<pkg_root>/phase2/pages/**` (o `pages/**` isolato) | PHASE2/UI | mantieni entrypoints stabili; shims sugli import |

## Import shims strategy

### Obiettivi

- Preservare import legacy (interni/esterni) durante le tranche.
- Rendere la deprecazione **visibile** (warning) ma non bloccante.
- Consentire una rimozione controllata con gate `-W error::DeprecationWarning`.

### Tipi di shim

1. **Module shim** (file singolo):
   - `old/path/foo.py` diventa uno stub che fa `from <new.path.foo> import *` + warning.
2. **Package shim** (`__init__.py`):
   - re-export mirati e lazy import (`__getattr__`) se necessario.
3. **Alias shim** (runtime):
   - `sys.modules['old.path'] = new_module` (solo se necessario; da evitare per auditability).

### Regole shim

- Ogni shim deve:
  - emettere `DeprecationWarning` con `stacklevel=2`.
  - essere tracciato nel TODO della tranche che lo introduce.
  - avere una data/criterio di rimozione (deprecation policy).

## Deprecation policy

- **Finestra minima**: 2 release minori successive (es. v1.2.6 e v1.2.7) oppure 60 giorni, scegliendo la maggiore.
- **Gate di rimozione**:
  1. Nessun import legacy rilevato con `rg "from <old_path>" -n` (o equivalente).
  2. Suite `pytest` PASS.
  3. Suite `pytest -W error::DeprecationWarning` PASS (solo quando si intende rimuovere).

## Protocollo tranche (operativo)

Per ogni tranche (WI fisico):

1. **Pre-flight**: eseguire G0 (baseline) e salvare log.
2. **Move + shims**: spostare file (solo nell’allowlist WI), introdurre shims, aggiornare import interni.
3. **Gates**: G1 → G2 → G3.
4. **Aggiornamento canonici** (solo allowlist): TODO, module registry, traceability, eventuali docs di fase.
5. **Evidence pack**: depositare log in `reports/` e aggiornare `.doc/LOGBOOK.md`.


## WI-0111 — Move Map final (virtual)

**Evidence:** `reports/WI-0111_move_map.md`

La Move Map è espressa come pattern *as-is → to-be* e definisce le tranche fisiche WI-0120..0160 (db/core/dataops/tools/pages) senza eseguire move in `src/`.

### Tranche map (fisico) — WI-0120..0160

| Tranche (WI) | Area | As-is pattern | To-be target | Fase |
|---|---|---|---|---|
| WI-0120 | db | `src/**/db/**` | `src/<pkg_root>/phase0/db/**` | PHASE0 |
| WI-0130 | core | `src/**/core/**` | `src/<pkg_root>/phase0/core/**` | PHASE0 |
| WI-0140 | dataops | `src/**/dataops/**` (+ `src/**/ingest/**` se presente) | `src/<pkg_root>/phase1/dataops/**` (+ `phase1/ingest/**`) | PHASE1 |
| WI-0150 | tools | `src/**/tools/**` | `src/<pkg_root>/phase0/tools/**` | PHASE0 |
| WI-0160 | pages | `src/**/pages/**` e/o `pages/**` | `src/<pkg_root>/phase2/pages/**` (oppure `pages/` resta root) | PHASE2/UI |

**Note:** i dettagli operativi shims/deprecation sono finalizzati in WI-0112.

## Rollback plan

- Ogni tranche crea un checkpoint git:
  - `tag pre-<WI>` prima dei move.
  - `tag post-<WI>` dopo gates PASS.
- In caso di failure:
  1. `git reset --hard pre-<WI>` (rollback rapido), oppure `git revert` della tranche se si preferisce mantenere cronologia.
  2. Ripetere G0 per confermare ritorno a stato sano.
- I log in `reports/` restano come evidenza, anche in caso di rollback.

## Expected logs (naming convention)

Per ogni WI/tranche, questi file sono attesi (minimo):

- `reports/pytest_tranche_<WI>.log`
- `reports/import_smoke_<WI>.log` (o nota se non applicabile)
- `reports/guardian_lint_<WI>.log`
- `reports/build_master_md_<WI>.log`

## Open points (da chiudere in WI-0110)

- Identificare `pkg_root` reale (es. `observer`) e path effettivi delle aree.
- Confermare quali tools appartengono a PHASE1 (batch) vs PHASE2 (UI/dev).
- Verificare dove vivono le pages Streamlit (root `pages/` vs package) per minimizzare churn.

<!-- WI-0112:BEGIN -->
### Import shims plan (WI-0112) — auto
- Report: `reports/WI-0112_shims_policy.md`
- Default shim: module stub + `DeprecationWarning` (`stacklevel=2`) + re-export.
- Deprecation stages: T0 introduce shims; T1 warnings enforced; T2 removal gate (`-W error::DeprecationWarning`).
- Planning-only: no changes to `src/**` or `tests/**` in WI-0112.
<!-- WI-0112:END -->
