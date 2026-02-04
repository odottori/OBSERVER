# TECH — Operational Technical Brief

> GENERATED FILE — DO NOT EDIT  
> Source of truth: `./docs/`  
> Generated: 2026-02-04T07:14:17Z  
> Fingerprint: 3ca08cf18ee7e88f

## Sources
- `docs/003_PDD_OBSERVER.md`
- `docs/008_EVIDENCE_PACK.md`
- `docs/005_TRACEABILITY_MATRIX.md`

---
## 2. Architettura a layer

### 2.1 Entry points (CLI / ops)
- `scripts/sentinel.py`: orchestrazione (migrate/test/run/certify/verify/forecast/status)
- `scripts/news_alpha.py`: NEWS-ALPHA runner (collect/run/status)
- `scripts/execute.py`: execution runner (paper-first)
- `scripts/ops_run_session.py` / `scripts/pack_session.py`: workflow e packaging deterministico
- `scripts/guardian.py`: governance documentale (direct mode)
  - `py scripts/guardian.py gate --wi WI-XXXX --mode normal|close`: gate suite con log in `reports/` (Collector B integrato)
  - `py scripts/guardian.py collect --wi WI-XXXX --mode normal|close`: validazione presenza/emptiness log WI
  - `py scripts/guardian.py docs-check --mode warn|hard`: check offline integrità link/anchors (log: `reports/docs_check_<WI>.log`)

### 2.2 Application layer (`src/`)
- `src/db/*`: schema owner + connection + audit store
- `src/core/*`: audit engine, cost/tax, ticker normalization
- `src/news_alpha/*`: ingest/scoring/dedup + persistence
- `src/forecast/ranking.py`: forecast/stars/ranking deterministici
- `src/risk/risk_engine.py`: risk gate (baseline) → evoluzione v1.2.5
- `src/execution/paper_broker.py`: paper broker baseline (orders/fills)
- `src/monitoring/*`: metriche e controlli operativi (baseline)

### 2.3 Presentation layer (UI)
- `app.py` + `pages/*`: console Streamlit (status, runs, ranking, monitoring).


## 3. Dataflow end-to-end

1) **Signals**: `recs` (analyst/news-derived) + eventuali staging tables  
2) **Normalization & mapping**: `ticker_mappings` time-bounded + normalizzazione SQL  
3) **Universe filter**: `universe_membership` (survivorship-bias control)  
4) **Timing & feasibility**: join con `prices` e regola conservativa `MIN(prices.date) > signal_date`  
5) **Audit/backtest**: produce `audit_trades` + `audit_equity` con costi/tasse  
6) **Forecast**: calibrazione su `audit_trades` → ranking deterministico + stars  
7) **Risk gate**: ranking → proposte ordini → decisioni ammessi/negati (reason_code)  
8) **Execution (paper)**: scrive `execution_orders` / `execution_fills`  
9) **Monitoring**: KPI e anomaly detection su dati/execution/modello  
10) **UI**: drill-down e controllo operativo.


### 2.1 Entry points (CLI / ops)
- `scripts/sentinel.py`: orchestrazione (migrate/test/run/certify/verify/forecast/status)
- `scripts/news_alpha.py`: NEWS-ALPHA runner (collect/run/status)
- `scripts/execute.py`: execution runner (paper-first)
- `scripts/ops_run_session.py` / `scripts/pack_session.py`: workflow e packaging deterministico
- `scripts/guardian.py`: governance documentale (direct mode)
  - `py scripts/guardian.py gate --wi WI-XXXX --mode normal|close`: gate suite con log in `reports/` (Collector B integrato)
  - `py scripts/guardian.py collect --wi WI-XXXX --mode normal|close`: validazione presenza/emptiness log WI
  - `py scripts/guardian.py docs-check --mode warn|hard`: check offline integrità link/anchors (log: `reports/docs_check_<WI>.log`)


## Repo Inventory (auto)

### scripts/
- `scripts/build_all_docs.py`
- `scripts/build_master_md.py`
- `scripts/doc_integrity_check.py`
- `scripts/docs_contract_check.py`
- `scripts/execute.py`
- `scripts/gen_mkdocs_views.py`
- `scripts/guardian.py`
- `scripts/guardian_next.py`
- `scripts/guardian_ops.py`
- `scripts/guardian_reset.py`
- `scripts/make_ai_input_pack.py`
- `scripts/make_phase2a_kickstart_pack.py`
- `scripts/news_alpha.py`
- `scripts/ops_reset.py`
- `scripts/ops_run_session.py`
- `scripts/pack_session.py`
- `scripts/patch_persist_equity.py`
- `scripts/phase01_dataops/_reference/EXEC_DataQuality_REFERENCE.py`
- `scripts/phase01_dataops/_reference/EXEC_Download_REFERENCE.py`
- `scripts/sentinel.py`
- `scripts/serve_code_docs.py`
- `scripts/setup.py`
- `scripts/wi_gate_runner.py`
- `scripts/wi_log_collector.py`

### pages/
- `pages/00_Decision_Briefing.py`
- `pages/01_Pipeline_Control.py`
- `pages/02_Gates_Data_Quality.py`
- `pages/03_Audit_Runs.py`
- `pages/04_Trades_Equity.py`
- `pages/05_Data_Gaps_Backfill.py`
- `pages/06_Forecasts_Ranking.py`
- `pages/07_NEWS_ALPHA.py`
- `pages/08_Lifecycle_Monitor.py`
- `pages/09_Execution_Log.py`
- `pages/10_Monitoring_TCA.py`
- `pages/11_DataOps_Control_Room.py`

### src/
- `src/__init__.py`
- `src/analyst_auditor.py`
- `src/compat/__init__.py`
- `src/compat/shims.py`
- `src/core/__init__.py`
- `src/core/alert_lifecycle.py`
- `src/core/audit_engine.py`
- `src/core/cost_model.py`
- `src/core/sentiment.py`
- `src/core/tax_model.py`
- `src/core/ticker_normalize.py`
- `src/data/__init__.py`
- `src/data/price_backfill.py`
- `src/dataops/__init__.py`
- `src/dataops/closures_seed.py`
- `src/dataops/common.py`
- `src/dataops/dq_prices.py`
- `src/dataops/halts_sync.py`
- `src/dataops/paths.py`
- `src/dataops/prices_ingest.py`
- `src/db/__init__.py`
- `src/db/audit_store.py`
- `src/db/connection.py`
- `src/db/migrate.py`
- `src/execution/__init__.py`
- `src/execution/paper_broker.py`
- `src/forecast/__init__.py`
- `src/forecast/ranking.py`
- `src/intelligence_engine.py`
- `src/monitoring/__init__.py`
- `src/monitoring/__main__.py`
- `src/monitoring/tca_report.py`
- `src/morning_bulletin.py`
- `src/news_alpha/__init__.py`
- `src/news_alpha/collect_google_news_rss.py`
- `src/news_alpha/db.py`
- `src/news_alpha/fixtures.py`
- `src/news_alpha/logging_utils.py`
- `src/news_alpha/observer.py`
- `src/news_alpha/run.py`
- `src/news_alpha/sentiment.py`
- `src/performance_analyzer.py`
- `src/phase0/__init__.py`
- `src/phase0/core/__init__.py`
- `src/phase0/core/alert_lifecycle.py`
- `src/phase0/core/audit_engine.py`
- `src/phase0/core/cost_model.py`
- `src/phase0/core/sentiment.py`
- `src/phase0/core/tax_model.py`
- `src/phase0/core/ticker_normalize.py`
- `... (+60 more)`
