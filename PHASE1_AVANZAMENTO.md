# OBSERVER — PHASE1 (DataOps) — Avanzamento consolidato

**Data:** 2026-01-30 (Europe/Rome)

Questo file serve a **consolidare** lo stato del checkpoint PHASE1 e permettere di ripartire senza perdere contesto.

---

## Cosa è stato completato (PHASE1)

### 1) DQ prezzi halt-aware + persistenza risultati
- File: `src/dataops/dq_prices.py`
- DQ “halt-aware”:
  - calendario business-day
  - esclusioni da `market_halts` e `ticker_halts`
  - findings: `PRICE_MISSING`, `PRICE_STALE`
  - invalid rows: `price IS NULL OR price <= 0`
- Persistenza su DB:
  - `dq_runs`
  - `dq_findings` (idempotente per `run_id`)
  - `dq_metrics_daily` (idempotente per `run_id`, market=`ALL` + rollup per market)

### 2) Migrazione schema DB (DuckDB)
- File: `src/db/migrate.py`
- Aggiunte tabelle:
  - `dq_runs`
  - `dq_findings`
  - `dq_metrics_daily`

### 3) CLI tools DataOps
Creati i wrapper ufficiali (modulo `-m`) sotto `src/tools/`:
- `dataops_import_closures.py` (seed da `borse_chiusure_storiche.csv` → `market_halts`)
- `dataops_sync_halts.py` (sync overlay `halts.yml` → `market_halts`/`ticker_halts`)
- `dataops_prices_ingest.py` (ingest incrementale prezzi via `PriceBackfiller`)
- `dataops_dq_prices.py` (run DQ prezzi)
- `dataops_status.py` (snapshot stato DataOps)

### 4) Streamlit Control Room
- Creata pagina: `pages/11_DataOps_Control_Room.py`
- Funzioni:
  - editor+save di `config/dataops/halts.yml` (validazione YAML)
  - bottoni: import closures / sync halts / ingest prezzi / dq prezzi
  - viste su tabelle: `dq_runs`, `dq_metrics_daily`, `dq_findings`, `data_gaps`

### 5) Docs pipeline e MkDocs
- Fix `scripts/build_all_docs.py` (bug di indentazione che rompeva la pipeline).
- Aggiornato `scripts/gen_mkdocs_views.py`:
  - aggiunta colonna `PHASE` nell’indice
  - generate pagine aggregate: `modules/_generated/PHASE1.md` e `PHASE2.md`
- Aggiornato `mkdocs/mkdocs.yml` nav per linkare le pagine di PHASE.

---

## Come eseguire (PowerShell / Windows)

> Nota: usa `py` (come da tua convenzione).

### Seed closures (borse_chiusure_storiche.csv → market_halts)
```powershell
py -m src.tools.dataops_import_closures --db data/sentinel_alpha.db
```

### Sync overlay halts.yml → DB
```powershell
py -m src.tools.dataops_sync_halts --db data/sentinel_alpha.db
```

### Ingest incrementale prezzi
```powershell
py -m src.tools.dataops_prices_ingest --db data/sentinel_alpha.db --asof 2026-01-30
```

### Run DQ prezzi
```powershell
py -m src.tools.dataops_dq_prices --db data/sentinel_alpha.db --asof 2026-01-30 --window-days 365
```

### Snapshot
```powershell
py -m src.tools.dataops_status --db data/sentinel_alpha.db
```

### Streamlit
```powershell
streamlit run pages/11_DataOps_Control_Room.py
```

---

## Cosa manca per “chiudere PHASE1” (deliverable v1.2.5)

6) Aggiornare canonici (`docs/002_PDR_OBSERVER.md`, `docs/004_DDT_DATADICTIONARY.md`, `docs/005_TRACEABILITY_MATRIX.md`, `docs/010_MODULE_REGISTRY.md`) e rigenerare `docs/OBSERVER_v1.2.5.md`.

7) Rigenerare PDF v1.2.5 con progetto LaTeX clean (pipeline pandoc → pdflatex) in modo chirurgico.

8) Aggiungere test minimi PHASE1 e lanciare `pytest`, salvando il log evidenza.

9) Produrre ZIP finale “pronto” + lista file obsoleti da rimuovere.

---

## File modificati / aggiunti in questo consolidamento

**Modificati:**
- `src/dataops/dq_prices.py`
- `src/db/migrate.py`
- `scripts/build_all_docs.py`
- `scripts/gen_mkdocs_views.py`
- `mkdocs/mkdocs.yml`

**Nuovi:**
- `src/tools/dataops_import_closures.py`
- `src/tools/dataops_sync_halts.py`
- `src/tools/dataops_prices_ingest.py`
- `src/tools/dataops_dq_prices.py`
- `src/tools/dataops_status.py`
- `pages/11_DataOps_Control_Room.py`
- `PHASE1_AVANZAMENTO.md`
