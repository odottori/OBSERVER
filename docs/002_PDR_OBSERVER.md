---
doc_id: 002_PDR_OBSERVER
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-30
---
# PDR — OBSERVER 2.0 (v1.2.5)

Build date: 2026-01-30

## 1. Executive summary

OBSERVER è una piattaforma “retail advanced” per:
- generare segnali (NEWS-ALPHA / analyst recs)
- trasformarli in ranking deterministici (stars + confidence)
- produrre audit trail e verificabilità (no future leak, provenance, run_id, fingerprint)
- abilitare progressivamente operatività **paper-first** e, in estensione, **live** con broker adapter
- garantire **DataOps** ripetibili (ingest, halt governance, DQ) per stabilità operativa e certification-grade runs

Il requisito primario è la **governance operativa**: ogni azione deve essere auditabile, riproducibile e “safe-by-design”.

## 2. Target user e scenari

### 2.1 Retail avanzato disciplinato
Vuole un workflow giornaliero/settimanale ripetibile, controlli rischio, e trasparenza (perché buy/skip?).

### 2.2 Builder / quant retail
Vuole estendere universi/dati/modelli, ma con vincoli di audit e regressione (test, schema versionato, lint).

### 2.3 Scenari applicativi (v1.2.5)
Gli scenari operativi sono formalizzati in:
- `docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md`

**Policy di roadmap:** prima si chiude il Layer “Operational Safety” (Risk/OMS/Execution/Monitoring), poi si scala su scenari alpha aggiuntivi.

## 3. Scope


### 3.0 Modello di delivery “per fasi” (Phase0/Phase1/Phase2)

Per ridurre rischio e “refactor anxiety”, OBSERVER viene governato **per fasi consegnabili** (non per processi).
L’obiettivo è che ogni fase abbia:
- scope chiaro (cosa include / cosa esclude)
- entrypoint stabili
- superficie DB dichiarata (tabelle lette/scritte)
- gate minimi ripetibili (lint/test/verify)

#### Tassonomia fasi (v1.2.5)

| Phase | Tag | Intento | Output principali | Gate minimi |
|---|---|---|---|---|
| Phase0 | `PHASE0_FOUNDATION` | Fondazioni + governance | schema DuckDB, config, tooling guardian/verify | `guardian lint` + migrate/verify |
| Phase1 | `PHASE1_DATAOPS` | Stabilità dati prezzi (halt-aware) | `prices`, `market_halts`, `ticker_halts`, DQ persistente | ingest offline + DQ + test minimi |
| Phase2 | `PHASE2_EXECUTION` | Paper-first execution + risk + monitoring | `execution_orders/fills`, audit trade/equity, monitoring/TCA | pytest + verify_run + (paper) execute |

> Nota: NEWS-ALPHA e Forecast-Ranking sono pipeline “signal plane” che appoggiano su Phase0/1; non sono considerate “Fase di delivery” autonoma in v1.2.5.

#### Definition of Done (DoD) per fase

- **Phase0 (Foundation)**: DB migrate stabile, path DB canonical, tool `db_status`/`verify_*` operativi, governance (`guardian`) green.
- **Phase1 (DataOps)**: ingest prezzi + gestione halts + DQ halt-aware con persistenza (`dq_*`), evidenza test PHASE1.
- **Phase2 (Execution)**: paper execution coerente + risk gate minimo + monitoring base (TCA/metrics) + audit trail end-to-end.

#### Entrypoint “as-built” per fase (snapshot)

- **Phase0 — Foundation/Governance**
  - CLI/tools: `py -m src.tools.db_status`, `py -m src.tools.verify_run`, `py -m src.tools.verify_provenance`
  - Scripts: `py scripts/sentinel.py status|verify|migrate`, `py scripts/guardian.py lint|next`
- **Phase1 — DataOps**
  - CLI/tools: `py -m src.tools.dataops_status`, `dataops_prices_ingest`, `dataops_sync_halts`, `dataops_import_closures`, `dataops_dq_prices`
  - UI: `pages/11_DataOps_Control_Room.py`, `pages/02_Gates_Data_Quality.py`, `pages/05_Data_Gaps_Backfill.py`
- **Phase2 — Execution/Risk/Monitoring**
  - Script: `py scripts/execute.py --paper`
  - UI: `pages/09_Execution_Log.py`, `pages/10_Monitoring_TCA.py`, `pages/08_Lifecycle_Monitor.py`

#### Policy release (operativa)

- **Release NODATA**: include codice+docs+test, **esclude** `data/` (DB) e `.venv/`.
- **Release WITH_DB**: include anche `data/sentinel_alpha.db`, **esclude** `.venv/`.


### 3.1 In-scope (v1.2.5)
- Data layer DuckDB (schema versionato + audit tables)
- **PHASE1 DataOps (stabilità dati prezzi)**:
  - seed closures → `market_halts`
  - overlay halts YAML → `market_halts` / `ticker_halts`
  - ingest incrementale prezzi (PriceBackfiller)
  - DQ prezzi **halt-aware** con persistenza (`dq_runs`, `dq_findings`, `dq_metrics_daily`)
  - Streamlit Control Room DataOps (editing `halts.yml` + run buttons + viste tabelle)
- Runner CLI: sentinel/news_alpha/forecast/execute (paper), pack_session, ops workflow
- Risk gate baseline e paper execution baseline (già presenti) da evolvere
- Monitoring base + UI Streamlit multi-pagina

### 3.2 Out-of-scope (perimetro *non* incluso come requisito chiuso in v1.2.5)
- Broker live production-ready (richiede adapter specifici e test con broker)
- Intraday / microstruttura / HFT
- Dataset proprietari/licenziati non inclusi
- Consulenza finanziaria o fiscale (solo educational tooling + disclaimer)

## 4. Requisiti funzionali (FR)

### FR-01 Offline-by-default
Nessuna chiamata rete senza `--online` o equivalente.

**Acceptance:** runner in assenza di flag opera senza rete e documenta la modalità.

### FR-02 Audit run tracciabile
Ogni run deve avere `run_id`, transcript, e `code_fingerprint`.

**Acceptance:** artefatti in `reports/` e record in `audit_runs`.

### FR-03 No future leak (conservativo)
Le regole T+1 e la logica di enterability devono essere verificabili e registrate.

**Acceptance:** per segnali data D, entry non può essere <= D; reason_code esplicito.

### FR-04 Determinismo e stabilità ranking
A parità di dati e codice, ranking identico (tie-break deterministici).

**Acceptance:** sort stabile; output JSON con ordering invariato.

### FR-05 Risk Engine (pre-trade e post-trade) — v1.2.5
Il sistema deve implementare un **modulo esplicito** di risk management separato dal ranking.

**Stato as-built:** presente gate base (cash reserve + max_positions + sizing statico).  
**Target v1.2.5 (minimo operativo):**
- pre-trade: sizing (risk-aware), limiti concentrazione, liquidity/turnover caps
- post-trade: stop-loss/trailing (ATR-based o equivalente), cooldown, kill-switch
- output: decision list con reason_code e parametri applicati

**Acceptance (v1.2.5):**
- esiste una funzione/entrypoint che, dato ranking + portafoglio, produce ordini ammessi/negati
- stop-loss genera exit orders con audit trail
- kill-switch blocca nuove aperture e forza riduzione rischio secondo policy

### FR-06 OMS + Execution log (paper-first) — v1.2.5
Il sistema deve registrare l’intero lifecycle ordine/fill e lo stato posizione.

**Stato as-built:** paper execution scrive `execution_orders`/`execution_fills`.  
**Target v1.2.5:**
- OMS minimale: order states (CREATED/SUBMITTED/FILLED/REJECTED/CANCELLED)
- posizione/PNL accounting (cash, holdings, realized/unrealized)
- reconciliation e idempotenza (no double fills, run_id consistent)

**Acceptance (v1.2.5):**
- `scripts/execute.py` genera ordini e aggiorna posizioni
- esiste report di execution (fills, fees, slippage model) e ledger aggiornato

### FR-07 Behavioral guardrails (“discipline mode”) — v1.2.5
Il sistema deve prevenire misuse retail (override non controllati).

**Acceptance:**
- regole minime: cooling-off, max loss day/week, override logging con motivazione
- modalità “hard blocks” configurabile

### FR-08 Monitoring & alerting — v1.2.5
Monitoraggio operativo e di modello (drift) con allarmi.

**Acceptance:**
- anomaly alerts: execution anomalies, data gaps, schema mismatch
- model health: rolling metrics (hit-rate, IC proxy, forecast vs realized)
- alert center (UI o log) con soglie configurabili

### FR-09 PHASE1 DataOps — prezzi: ingestion, halt governance, DQ (halt-aware)
Il sistema deve offrire un workflow ripetibile per:
- governare le chiusure/halts di mercato e ticker (seed + overlay) con provenienza
- ingest incrementale prezzi (con data_gaps) senza corrompere il DB
- eseguire controlli DQ su calendario business-day **escludendo** gli intervalli in `market_halts` e `ticker_halts`
- persistere i risultati DQ in tabelle dedicate (`dq_runs`, `dq_findings`, `dq_metrics_daily`) in modo idempotente

**Acceptance (PHASE1):**
- CLI DataOps disponibili come moduli `-m src.tools.*` + pagina Streamlit `pages/11_DataOps_Control_Room.py`
- un run DQ produce record coerenti e ripetibili (run_id idempotente) in `dq_*`

## 5. Requisiti non funzionali (NFR)

- Riproducibilità (run deterministiche salvo timestamp)
- Robustezza (data gaps non corrompono DB; circuit breaker)
- Trasparenza (reason_code per ogni decisione)
- Sicurezza (segreti via env; no hardcoding)
- Portabilità (Windows/PowerShell supportata: `py`)

## 6. Definition of Done (DoD) v1.2.5

- `005_TRACEABILITY_MATRIX.md` copre 100% componenti rilevanti
- `guardian lint` senza errori
- `pytest` passa nello snapshot (inclusi test minimi PHASE1 DataOps)
- `sentinel/news_alpha/forecast/execute` eseguono su DB presente
- evidenze in `008_EVIDENCE_PACK.md` eseguibili e coerenti

## 7. Piano implementativo (esaustivo e strutturato)

### Milestone M0 — Baseline certificabile (già esistente)
- audit/backtest/ranking deterministici, offline-by-default, UI base

### Milestone M1 — “Operational Safety” per Scenario 1 (paper robusto)
Obiettivo: scenario 1 eseguibile in paper con controlli rischio e audit completi.

Deliverable:
- RiskEngine v1 (pre+post trade: stop/trailing/cooldown/kill-switch)
- OMS minimale con posizione/PNL accounting
- Paper execution con slippage model base + TCA report
- Guardrails minimi (discipline mode)
- Monitoring base + alerting (execution/data gaps)

Acceptance:
- un utente può selezionare ranking e vedere ordini simulati, controllati e registrati
- stop-loss genera exit con audit trail
- session pack deterministico con report execution

### Milestone M2 — Alpha expansion controllata (Scenario 2)
Deliverable:
- factor library estesa (minimo: value/quality con definizioni e governance)
- dynamic weighting (regime-aware “base”)
- attribution “minimo” per fattore e per contributo a return

Acceptance:
- ranking multi-factor riproducibile + report attribution

### Milestone M3 — Event-driven (Scenario 3) — solo dopo dati affidabili
Deliverable:
- corporate actions collector + event engine (conservative timing)
- risk limits event-driven

### Milestone M4 — Macro/Rotation e strategie avanzate (Scenari 4–5)
Solo dopo stabilizzazione execution/risk/monitoring.

## 8. Rischi e mitigazioni (realistiche)

- Paper troppo ottimista → slippage/spread model early + stress test
- Data gaps live → circuit breaker + procedure override tracciata
- Alpha decay → OOS rigoroso + monitoring; nessuna promessa di performance
- Regulatory/communication → disclaimer chiaro + educational stance
