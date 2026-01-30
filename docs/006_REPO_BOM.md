---
doc_id: 006_REPO_BOM
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-26
---
# Repository BOM (Bill of Materials) — v1.2.5

Build date: 2026-01-26

## 1. Scopo

Inventario dei componenti *as-built* nello snapshot repository, con focus su ciò che è rilevante per:
- pipeline operativa (runner CLI)
- UI Streamlit
- moduli core (audit/forecast/news)
- risk & execution (paper-first)
- governance docset (GUARDIAN)

## 2. Struttura ad alto livello

- `app.py` — entrypoint Streamlit (UI)
- `main.py` — orchestrazione CLI/batch
- `scripts/` — runner e utility operative (sentinel/news/execute/ops/guardian)
- `src/` — logica applicativa
- `data/` — DuckDB locale e file di supporto
- `reports/` — artefatti e session logs (per riproducibilità)
- `.doc/` — libreria documentale derivata (GUARDIAN)
- `docs/` — documentazione canonica e PDF

## 3. Runner e utility (scripts/)

| File | Ruolo |
|---|---|
| `scripts/sentinel.py` | Runner principale (migrate/test/run/certify/verify/forecast/status) |
| `scripts/news_alpha.py` | Runner NEWS-ALPHA (collect/run/status) |
| `scripts/execute.py` | Execution runner (paper-first) |
| `scripts/ops_run_session.py` | Workflow run→pack→certify→pack |
| `scripts/pack_session.py` | Packaging deterministico sessione |
| `scripts/ops_reset.py` | Reset operativo (news/sentinel) |
| `scripts/setup.py` | Bootstrap/repair cross-platform |
| `scripts/guardian.py` | Governance docset (sync/lint/derive/status) |

## 4. UI Streamlit (pages/)

| File | Ruolo |
|---|---|
| `pages/00_Decision_Briefing.py` | Decision briefing / sintesi |
| `pages/01_Pipeline_Control.py` | Controllo pipeline |
| `pages/02_Gates_Data_Quality.py` | Gates / data quality |
| `pages/03_Audit_Runs.py` | Audit runs |
| `pages/04_Trades_Equity.py` | Trades & equity |
| `pages/05_Data_Gaps_Backfill.py` | Data gaps / backfill |
| `pages/06_Forecasts_Ranking.py` | Forecasts / ranking |
| `pages/07_NEWS_ALPHA.py` | NEWS-ALPHA console |
| `pages/08_Lifecycle_Monitor.py` | Lifecycle / monitor |

## 5. Package applicativi (src/)

| Package | Contenuto |
|---|---|
| `src/core/` | audit engine, cost model, tax model, ticker normalization |
| `src/db/` | schema owner + connection + audit store |
| `src/news_alpha/` | collect, deterministic sentiment, persistence |
| `src/forecast/` | stars/ranking (Wave 6) |
| `src/risk/` | risk gate (baseline) |
| `src/execution/` | paper broker baseline |
| `src/monitoring/` | monitor/metrics (baseline) |
| `src/tools/` | verify utilities e diagnostica |
| `src/data/` | helper per data layer |

## 6. Note di release “pulita”

Per packaging distributivo si raccomanda di escludere:
- `__pycache__/`, `*.pyc`
- `reports/` storici non necessari (includere solo evidence pack selezionato)
- `.old/` e snapshot storici
