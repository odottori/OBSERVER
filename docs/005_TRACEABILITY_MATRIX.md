# Traceability Matrix (Repo -> Docset) — v1.2.5

Build date: 2026-02-03

## Scopo

Questa matrice garantisce che:

- nessun componente rilevante del repository sia “orfano” (non descritto)
- ogni sezione documentale rimandi a componenti reali
- la completezza sia verificabile tramite comandi e artefatti


## 0) Document set governance

| Documento | Stato | Scopo |
|---|---|---|
| docs/000_README_DOCSET.md | CANONICO | Indice e regole del docset |
| docs/002_PDR_OBSERVER.md | CANONICO | Requisiti + piano implementativo |
| docs/009_GAP_REGISTER.md | CANONICO | Gap/backlog allineato a v1.2.5 |
| docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md | SUPPORTO | Scenari concreti e valutazione realistica |

## 0.1) Vista per fasi (delivery taxonomy)

La matrice sottostante organizza i componenti “as-built” in una vista **per fasi consegnabili**.
È una vista *ortogonale* rispetto ai capitoli A–K (che restano “per processo”).

| Phase | Tag | Cosa include | Sezioni principali in questa matrice |
|---|---|---|---|
| Phase0 | `PHASE0_FOUNDATION` | guardian/verify, schema DB, config, orchestrazione base | A, B, C, J, K |
| Phase1 | `PHASE1_DATAOPS` | ingest prezzi + halts + DQ persistente + Control Room | B2, I, K |
| Phase2 | `PHASE2_EXECUTION` | paper execution + risk + monitoring + audit end-to-end | D, I, K, (E audit) |
| Signal plane (supporto) | `PHASE2_SIGNAL` | NEWS-ALPHA + forecast/ranking + signal cache | F, G, I |


## A) Entrypoint e orchestrazione

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| app.py | Streamlit app entrypoint (routing UI pages) | IMPLEMENTATO | 001§8; 003§6 (UI) | `py -m streamlit run app.py` |
| main.py | CLI orchestrator (batch) | IMPLEMENTATO | 003§5 (Orchestrazione) | `py main.py --help` |

## B) Runner e utility operative (scripts/)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| scripts/sentinel.py | SENTINEL-ALPHA one-command runner. | IMPLEMENTATO | 001§5-6; specs/SENTINEL_RUNNER_SPEC; 008 | `py scripts/sentinel.py --help` |
| scripts/news_alpha.py | NEWS-ALPHA operator runner. | IMPLEMENTATO | 001§5; specs/NEWS_ALPHA_SPEC; 008 | `py scripts/news_alpha.py --help` |
| scripts/execute.py | Execution runner (paper broker) | IMPLEMENTATO | 002; 003 | `py scripts/execute.py --help` |
| scripts/ops_reset.py | Operational reset utility (NEWS-ALPHA / SENTINEL-ALPHA). | IMPLEMENTATO | 001§5/Appendice A; 003§7 (Ops); 008 | `py scripts/ops_reset.py --help` |
| scripts/ops_run_session.py | Run -> pack -> certify -> pack (DB-first auto-run-id). | IMPLEMENTATO | 001§5; 008 (session workflow) | `py scripts/ops_run_session.py --help` |
| scripts/pack_session.py | Pack reports into deterministic session folders (no symlinks). | IMPLEMENTATO | 008 (packaging); 003§7 | `py scripts/pack_session.py --help` |
| scripts/patch_persist_equity.py | Utility operativa | IMPLEMENTATO | 001§5/Appendice A; 003§7 (Ops); 008 | `py scripts/patch_persist_equity.py --help` |
| scripts/setup.py | SENTINEL-ALPHA bootstrap / repair entrypoint (cross-platform). | IMPLEMENTATO | 008 (bootstrap); 003§7 | `py scripts/setup.py --help` |

## B2) PHASE1 DataOps (stabilità dati prezzi)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/phase2/pages/11_DataOps_Control_Room.py (shim: pages/11_DataOps_Control_Room.py) | Pagina Streamlit (Control Room DataOps) | IMPLEMENTATO | 001§8; 003§6; 002 FR-09 | (UI) |
| src/phase0/dataops/prices_ingest.py (shim: src/dataops/prices_ingest.py) | DataOps: ingest incrementale prezzi + data_gaps | IMPLEMENTATO | 003§4 (Data layer); 008 | `py -m src.tools.dataops_prices_ingest --help` |
| src/phase0/dataops/halts_sync.py (shim: src/dataops/halts_sync.py) | DataOps: sync overlay halts YAML -> DB | IMPLEMENTATO | 003§4 (Data layer); 008 | `py -m src.tools.dataops_sync_halts --help` |
| src/phase0/dataops/closures_seed.py (shim: src/dataops/closures_seed.py) | DataOps: seed closure storiche -> market_halts | IMPLEMENTATO | 003§4 (Data layer); 008 | `py -m src.tools.dataops_import_closures --help` |
| src/phase0/dataops/dq_prices.py (shim: src/dataops/dq_prices.py) | DataOps: DQ prezzi halt-aware (missing/stale/invalid) | IMPLEMENTATO | 002 FR-09; 004 | `py -m src.tools.dataops_dq_prices --help` |
| src/phase0/tools/dataops_status.py (shim: src/tools/dataops_status.py) | Tool: stato DataOps (tabella counts + quick checks) | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.dataops_status --help` |
| src/phase0/tools/dataops_prices_ingest.py (shim: src/tools/dataops_prices_ingest.py) | Tool: runner ingest prezzi (offline-by-default) | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.dataops_prices_ingest --help` |
| src/phase0/tools/dataops_sync_halts.py (shim: src/tools/dataops_sync_halts.py) | Tool: runner sync halts (halts.yml) | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.dataops_sync_halts --help` |
| src/phase0/tools/dataops_import_closures.py (shim: src/tools/dataops_import_closures.py) | Tool: seed closures CSV -> market_halts | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.dataops_import_closures --help` |
| src/phase0/tools/dataops_dq_prices.py (shim: src/tools/dataops_dq_prices.py) | Tool: runner DQ prezzi (halt-aware) | IMPLEMENTATO | 002 FR-09; 004 | `py -m src.tools.dataops_dq_prices --help` |
| config/dataops/* | Config DataOps (closures seed, mapping, halts overlay) | IMPLEMENTATO | 003§7 (Ops); 008 | (usato dai runner) |


## C) Data layer (DuckDB + migrazioni)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/phase0/db/migrate.py (shim: src/db/migrate.py) | Schema owner + migrations DuckDB | IMPLEMENTATO | 004; 003§4 (Data layer) | `py -m src.db.migrate --db data/sentinel_alpha.db` |
| src/phase0/db/connection.py (shim: src/db/connection.py) | Connection helper (DbConfig/connect) | IMPLEMENTATO | 003§4 | (usato dai runner) |
| src/phase0/db/audit_store.py (shim: src/db/audit_store.py) | Persistence layer per audit artifacts | IMPLEMENTATO | 003§4-5; 008 | (invocato dai runner) |
| data/sentinel_alpha.db | DuckDB local store (schema v2.1.0) | IMPLEMENTATO | 004; 008 | `py scripts/sentinel.py status` |
| test/test_db_migrate.py | Test: idempotenza schema + seed + tabelle execution_* | IMPLEMENTATO | 004 | `py -m pytest test/test_db_migrate.py` |

## D) Execution + Risk + Monitoring

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/execution/paper_broker.py | Paper broker: ranking -> orders/fills (+ risk flags) | IMPLEMENTATO | 002; 003 | `py -m pytest test/test_execute_paper.py` |
| test/test_execute_paper.py | Test: paper broker crea orders/fills e gestisce REJECTED | IMPLEMENTATO | 002; 003 | `py -m pytest test/test_execute_paper.py` |
| src/risk/risk_engine.py | RiskEngine v0 (pre-trade gate) | IMPLEMENTATO | 002; 003 | `py -m pytest test/test_risk_engine.py` |
| test/test_risk_engine.py | Test: RiskEngine v0 reason_code deterministico | IMPLEMENTATO | 002; 003 | `py -m pytest test/test_risk_engine.py` |
| src/monitoring/tca_report.py | Monitoring/TCA v0 report (slippage/fees/cost-drag + hit-rate) | IMPLEMENTATO | 002; 003 | `py -m src.monitoring --help` |
| src/monitoring/__main__.py | CLI Monitoring/TCA v0 | IMPLEMENTATO | 002; 003 | `py -m src.monitoring --help` |
| test/test_tca_report.py | Test: TCA report deterministico + alert | IMPLEMENTATO | 002; 003 | `py -m pytest test/test_tca_report.py` |

## D2) Cluster PHASE2_EXECUTION (paper-first)

Questo cluster rappresenta la fase “delivery” Phase2:
- risk gate pre-trade (minimo)
- paper execution (order/fill logging)
- monitoring base + TCA
- audit trail end-to-end

**Entrypoint chiave:**
- `py scripts/execute.py --paper`
- UI: `pages/09_Execution_Log.py`, `pages/10_Monitoring_TCA.py`, `pages/08_Lifecycle_Monitor.py`

**Superficie DB:** `execution_orders`, `execution_fills`, `audit_runs`, `audit_trades`, `audit_equity`.


## E) Core engine (src/core)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/phase0/core/audit_engine.py (shim: src/core/audit_engine.py) | Audit engine (no future leak, trades, equity) | IMPLEMENTATO | 001§6; specs/AUDIT_LIFECYCLE_SPEC; 003§5 | `py scripts/sentinel.py run --help` |
| src/phase0/core/alert_lifecycle.py (shim: src/core/alert_lifecycle.py) | Lifecycle monitor (TRADABLE/WAITLIST/EXPIRED + traded states) | IMPLEMENTATO | 001§6; specs/AUDIT_LIFECYCLE_SPEC | `py -m src.tools.alert_lifecycle --help` |
| src/phase0/core/cost_model.py (shim: src/core/cost_model.py) | Retail cost model (round-trip cost) | IMPLEMENTATO | 003§8 (Costi) ; 007 | (usato in audit_engine) |
| src/phase0/core/tax_model.py (shim: src/core/tax_model.py) | Modello fiscale IT (CGT + loss carry) | IMPLEMENTATO | 003§8 (Tasse) ; 007 | (usato in audit_engine) |
| src/phase0/core/sentiment.py (shim: src/core/sentiment.py) | Sentiment helper (offline/deterministico) | IMPLEMENTATO | 003 | (usato da NEWS-ALPHA/forecast) |
| src/phase0/core/ticker_normalize.py (shim: src/core/ticker_normalize.py) | Ticker normalize helpers | IMPLEMENTATO | 003 | (usato da audit/forecast/tools) |

## F) Forecast

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/forecast/ranking.py | Forecast ranking a stelle (Wave 6) | IMPLEMENTATO | 001§7; specs/WAVE6_FORECAST...; 007 | `py -m src.tools.forecast_rankings --help` |

## G) NEWS-ALPHA (src/news_alpha)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/news_alpha/run.py | News ingestion + scoring + dedup + aggregation | IMPLEMENTATO | 001§5; specs/NEWS_ALPHA_SPEC; 007 | `py scripts/news_alpha.py run --help` |
| src/news_alpha/collect_google_news_rss.py | RSS collector (Google News) | IMPLEMENTATO | specs/NEWS_ALPHA_SPEC | (invocato da run) |
| src/news_alpha/db.py | Persistence layer NEWS-ALPHA | IMPLEMENTATO | 003§4 | (invocato da run) |

## H) Moduli applicativi (src/*.py)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/report_generator.py | Report generator (markdown) | IMPLEMENTATO | 001; 003 | `py -m pytest test/test_report_generator.py` |
| src/performance_analyzer.py | Performance analyzer | IMPLEMENTATO | 001; 003 | `py -m pytest test/test_performance_analyzer.py` |
| src/intelligence_engine.py | Intelligence engine (orchestrazione) | IMPLEMENTATO | 001; 003 | `py -m pytest test/test_analyst_auditor.py` |
| src/analyst_auditor.py | Analyst/Auditor orchestrator | IMPLEMENTATO | 001; 003 | `py -m pytest test/test_analyst_auditor.py` |
| src/morning_bulletin.py | Morning bulletin generator | IMPLEMENTATO | 001; 003 | `py -m pytest test/test_app_py_compile.py` |
| src/sentinel_alpha.py | Application module (sentinel alpha) | IMPLEMENTATO | 001; 003 | `py -m pytest test/test_sentinel_core.py` |

## I) UI Streamlit (pages/)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/phase2/pages/00_Decision_Briefing.py (shim: pages/00_Decision_Briefing.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/01_Pipeline_Control.py (shim: pages/01_Pipeline_Control.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/02_Gates_Data_Quality.py (shim: pages/02_Gates_Data_Quality.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/03_Audit_Runs.py (shim: pages/03_Audit_Runs.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/04_Trades_Equity.py (shim: pages/04_Trades_Equity.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/05_Data_Gaps_Backfill.py (shim: pages/05_Data_Gaps_Backfill.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/06_Forecasts_Ranking.py (shim: pages/06_Forecasts_Ranking.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/07_NEWS_ALPHA.py (shim: pages/07_NEWS_ALPHA.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/08_Lifecycle_Monitor.py (shim: pages/08_Lifecycle_Monitor.py) | Pagina Streamlit | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/09_Execution_Log.py (shim: pages/09_Execution_Log.py) | Pagina Streamlit (execution_orders/execution_fills + risk flags) | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/10_Monitoring_TCA.py (shim: pages/10_Monitoring_TCA.py) | Pagina Streamlit (TCA report) | IMPLEMENTATO | 001§8; 003§6 | (UI) |
| src/phase2/pages/11_DataOps_Control_Room.py (shim: pages/11_DataOps_Control_Room.py) | Pagina Streamlit (Control Room DataOps) | IMPLEMENTATO | 001§8; 003§6; 002 FR-09 | (UI) |

## J) GUARDIAN tooling (operativo)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| scripts/guardian.py | CLI entrypoint GUARDIAN (direct mode) | IMPLEMENTATO | 003§7 (Ops); 008 | `py scripts/guardian.py --help` |
| scripts/guardian_ops.py | Ops: init/sync/lint/derive/status (non-distruttivo) | IMPLEMENTATO | 003§7 (Ops); 008 | `py scripts/guardian.py status` |
| scripts/guardian_next.py | Executor: genera CURRENT_STATE da TODO; ripresa crash | IMPLEMENTATO | 003§7 (Ops); 008 | `py scripts/guardian.py next` |
| scripts/wi_gate_runner.py | One-command gate suite per WI (writes reports logs) | IMPLEMENTATO | 003§2.1; 008§8.1; 010 (MOD-GUARDIAN-DOCOPS) | `py scripts/guardian.py gate --wi WI-XXXX --mode normal` |
| scripts/wi_log_collector.py | Collector (B): check log presence/emptiness + hit patterns | IMPLEMENTATO | 008§8.1; 010 (MOD-GUARDIAN-DOCOPS) | `py scripts/guardian.py collect --wi WI-XXXX --mode normal` |
| scripts/doc_integrity_check.py | Tool: docs-check (validate markdown links/anchors) | IMPLEMENTATO | 003§2.1; 008§8.1; 010 (MOD-GUARDIAN-DOCOPS) | `py scripts/guardian.py docs-check --mode warn` |
| scripts/guardian_reset.py | Utility: reset/backup GUARDIAN (ops) | IMPLEMENTATO | 003§7 (Ops); 008 | `py scripts/guardian_reset.py --help` |
| .doc/TODO.md | Backlog WI (source operativa) | IMPLEMENTATO | (Ops) | `py scripts/guardian.py next` |
| .doc/CURRENT_STATE.md | Stato corrente + p0 | IMPLEMENTATO | (Ops) | `type .doc/CURRENT_STATE.md` |
| .doc/LOGBOOK.md | Diario transizioni (audit) | IMPLEMENTATO | (Ops) | `type .doc/LOGBOOK.md` |

## K) Tooling verifiche (src/phase0/tools)

| Componente (path) | Classe | Stato | Documentazione (ref) | Verifica rapida |
|---|---|---|---|---|
| src/phase0/tools/db_status.py (shim: src/tools/db_status.py) | Tool: DB status / introspection | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.db_status --help` |
| src/phase0/tools/verify_run.py (shim: src/tools/verify_run.py) | Tool: verify run artifacts | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.verify_run --help` |
| src/phase0/tools/verify_inputs.py (shim: src/tools/verify_inputs.py) | Tool: verify inputs | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.verify_inputs --help` |
| src/phase0/tools/verify_ticker_mappings.py (shim: src/tools/verify_ticker_mappings.py) | Tool: verify ticker mappings | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.verify_ticker_mappings --help` |
| src/phase0/tools/verify_provenance.py (shim: src/tools/verify_provenance.py) | Tool: verify provenance | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.verify_provenance --help` |
| src/phase0/tools/forecast_rankings.py (shim: src/tools/forecast_rankings.py) | Tool: forecast rankings | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.forecast_rankings --help` |
| src/phase0/tools/forced_exits.py (shim: src/tools/forced_exits.py) | Tool: forced exits analysis | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.forced_exits --help` |
| src/phase0/tools/ticker_mappings.py (shim: src/tools/ticker_mappings.py) | Tool: ticker mappings ops | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.ticker_mappings --help` |
| src/phase0/tools/universe_membership.py (shim: src/tools/universe_membership.py) | Tool: universe membership ops | IMPLEMENTATO | 003§7 (Ops); 008 | `py -m src.tools.universe_membership --help` |

## Regola di accettazione (operativa)

- **Coverage 100% sui componenti rilevanti**: runner, pipeline, data layer, UI, strumenti, tooling operativo.
- **Zero voci fantasma**: nulla è descritto come “presente” se non esiste nello snapshot.
- **Verifiche ripetibili**: per ogni runner esiste almeno un comando `--help` o `status` che conferma l’installazione.

### WI-0260 — Collector strict-hits profiles

- Requirement: Collector B supports profiles (`hardfail|deprec|none`) and strict-hits gate.
- Implementation: `scripts/wi_log_collector.py`, `scripts/wi_gate_runner.py`, `scripts/guardian.py`.
- Verification: `tests/test_wi_log_collector.py`, `tests/test_wi_gate_runner.py`.
