---
doc_id: 000_README_DOCSET
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-30
---
# OBSERVER Document Set (v1.2.5)

Build date: 2026-01-30

## Scopo del docset

Questo docset definisce e governa **OBSERVER 2.0** in modalità *auditability-first* e *offline-by-default*.

- `docs/` è la **source of truth**: i file Markdown canonici sono versionabili, diffabili e tracciabili.
- Il PDF `docs/OBSERVER_v1.2.5.pdf` è un **artefatto derivato** (render/packaging), non la sorgente primaria.
- La cartella `.doc/` contiene la **libreria canonica derivata** (brief PROJ/TECH/DDT) generata via GUARDIAN.

## Contenuti canonici

### Canonici (authoritative)
- `001_PROJECT_OVERVIEW.md`
- `002_PDR_OBSERVER.md`
- `003_PDD_OBSERVER.md`
- `004_DDT_DATADICTIONARY.md`

### Supporto (verificabilità)
- `005_TRACEABILITY_MATRIX.md`
- `006_REPO_BOM.md`
- `007_PARAMETER_SNAPSHOT.md`
- `008_EVIDENCE_PACK.md`
- `009_GAP_REGISTER.md`

### Specifiche tecniche
- `docs/specs/WAVE6_FORECAST_STARS_RANKING_SPEC.md`
- `docs/specs/SENTINEL_RUNNER_SPEC.md`
- `docs/specs/NEWS_ALPHA_SPEC.md`
- `docs/specs/AUDIT_LIFECYCLE_SPEC.md`

### Use-cases (supporto, scenario-driven)
- `docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md`

### PDF & sorgente LaTeX
- `docs/OBSERVER_v1.2.5.pdf`
- `docs/LATEX_zip/OBSERVER_LATEX_CLEAN_v1.2.5_PROJECT.zip`

## CONTRATTI DI GOVERNANCE (hard)

Queste regole sono **contratti**: se vengono violate, aumenta il rischio di drift e incoerenza.

1. **Canonici solo in `docs/`**  
   - I documenti canonici (*authoritative*) devono vivere **solo** in `docs/`.
   - La cartella `.doc/` è riservata ai **derivati GUARDIAN** (brief/manifest/ops), non è un secondo set di canonici.

2. **MkDocs è una VISTA derivata (mai source-of-truth)**  
   - `mkdocs/` contiene solo: configurazione, guide UI, API docs, e **stub** che includono i canonici da `docs/`.
   - È vietato mantenere copie “vive” dei canonici dentro `mkdocs/docs/` (es. `009_*.md`, `010_*.md`, ecc.).

3. **Artefatti duplicabili in MkDocs solo se NON canonici**  
   - Esempi: PDF, immagini, export HTML. Se copiati in `mkdocs/docs/`, devono essere considerati **artefatti derivati** e sincronizzati via script.

4. **Post-TODO update (derivato)**  
   - Dopo una patch/commit derivata da TODO (anche via prompt), si rigenerano solo i derivati:
     - GUARDIAN (`sync/lint/derive`), master MD, MkDocs build.
   - I canonici si aggiornano **solo** quando cambia realmente la specifica/piano, non “per riflesso”.

5. **Verificabilità**  
   - Se viene introdotta una mappa (gap↔todo↔moduli), deve essere **derivata** (generata) o single-source-of-truth nel TODO, mai duplicata manualmente in più file.

## Refactor Plan (virtual) — governance

- Prima di qualsiasi refactor fisico (WI-0104), si mantiene un piano virtuale in `docs/012_REFACTOR_PLAN_VIRTUAL.md` con **Move Map**, **import-shims**, **rollback** e **gates ripetibili per tranche**.
- Il refactor fisico avviene solo per tranche (1 tranche = 1 WI) con `pytest` sempre PASS.

## Regole operative (GUARDIAN - direct mode)

Comandi standard (PowerShell/Windows):

- Stato docset: `py scripts/guardian.py status`
- Allinea libreria canonica: `py scripts/guardian.py sync --clean`
- Lint strutturale: `py scripts/guardian.py lint`
- Deriva i brief: `py scripts/guardian.py derive`

**Regola d’oro:** se cambia il codice, si fa prima **as-built inventory + delta**, poi si aggiornano i canonici e infine si rigenera `.doc/`/manifest/checksum/PDF.


## Support documents
- `docs/010_MODULE_REGISTRY.md` — module registry (as-built + target)
- `docs/011_GAP_DERIVATION_MATRIX.md` — derived-gap matrix
- `docs/012_REFACTOR_PLAN_VIRTUAL.md` — refactor plan (virtual) + move-map + shims + tranche gates
