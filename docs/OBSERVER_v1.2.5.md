# OBSERVER 2.0 — Docset v1.2.5 (Markdown)

> Auto-assembled from the canonical documents in `docs/`.


---

## 000_README_DOCSET.md

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


---

## 001_PROJECT_OVERVIEW.md

---
doc_id: 001_PROJECT_OVERVIEW
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-26
---
# OBSERVER 2.0 — Project Overview (allineato al codice)

Build date: 2026-01-26

## 1. In una frase

**OBSERVER** è un sistema *offline-by-default* che raccoglie segnali (news/analyst), li sottopone a gate di qualità/provenance, esegue audit/backtest conservativi (no future leak) e produce **ranking deterministici** (stars + confidence) con evidenze riproducibili.

## 2. Il problema che risolve (retail avanzato)

- Backtest non auditabile (leakage, universi non controllati, risultati non riproducibili).
- Dati “sporchi” (ticker mapping, prezzi mancanti, sospensioni, corporate actions).
- Segnali non comparabili (fonti diverse senza calibrazione/confidence).
- Operatività opaca (mancanza di transcript, run_id, fingerprint del codice).

## 3. Stato attuale (as-built): cosa è già operativo

### 3.1 Decision & research engine (maturo)
- **Audit engine** con regole conservative e ledger (`audit_runs`, `audit_trades`, `audit_equity`).
- **NEWS-ALPHA** deterministico (ingest/score/dedup) con output riproducibile.
- **Forecast ranking (Wave 6)**: shrinkage + confidence + percentile-to-stars (`src/forecast/ranking.py`).
- **Cost model** e **tax model IT** per realismo retail (`src/core/*`).
- **UI Streamlit** per monitoraggio e ispezione (`app.py`, `pages/*`).

### 3.2 Operatività paper-first (baseline presente)
- **Paper execution baseline**: genera ordini e scrive `execution_orders` / `execution_fills` (`src/execution/paper_broker.py`, `scripts/execute.py`).
- **Risk gate baseline**: sizing statico + cash reserve + max positions (`src/risk/risk_engine.py`).

Questa baseline è sufficiente per “paper trading dimostrativo”, ma non ancora per paper **robusto** né per live.

## 4. Aree di completamento v1.2.5 (obiettivo: scenario 1 paper robusto)

1) **RiskEngine evoluto (pre+post trade)**: stop/trailing (es. ATR-based), kill-switch, cooldown, limiti concentrazione/liquidità.  
2) **OMS minimale**: lifecycle ordine/fill + posizioni/PNL accounting + reconciliation/idempotenza.  
3) **Execution realism**: slippage/spread model + TCA report (evitare paper troppo ottimista).  
4) **Monitoring & alerting**: anomaly (data gaps/execution) + model health (rolling metrics).  
5) **Guardrails retail**: “discipline mode” con hard blocks e override logging.

Scenari applicativi e valutazione realistica: `docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md`.

## 5. Architettura ad alto livello (layer)

| Layer | Componenti principali | Output |
|---|---|---|
| Data layer | DuckDB + migrations (`src/db/*`) | tabelle versionate + audit store |
| Signal layer | `src/news_alpha/*`, `recs`, mapping | segnali normalizzati e tracciati |
| Audit/Backtest | `src/core/*` | trades/equity + report |
| Forecast/Ranking | `src/forecast/ranking.py` | ranking deterministico + stars |
| Risk/Execution | `src/risk/*`, `src/execution/*` | ordini ammessi/negati + orders/fills |
| Monitoring/UI | `src/monitoring/*`, `app.py`, `pages/*` | dashboard, alert, drill-down |

## 6. Workflow operativo (tipico)

1) **Setup / migrate**: crea/aggiorna schema DuckDB.
2) **Run audit**: ingest segnali → gates → backtest conservativo → audit tables + report.
3) **Forecast**: calibrazione su storico → stars/ranking deterministici.
4) **Execute (paper)**: dal ranking → risk gate → orders/fills persistiti.
5) **Monitor**: KPI operativi (data gaps, execution anomalies) + health modello.

## 7. Nota su performance e promesse

Qualunque stima di alpha/sharpe è una **ipotesi di ricerca** e va trattata come tale:
validazione out-of-sample, costi/slippage conservativi e monitoring sono parte integrante del prodotto.


---

## 002_PDR_OBSERVER.md

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


---

## 003_PDD_OBSERVER.md

---
doc_id: 003_PDD_OBSERVER
docset_version: 1.2.5
status: canonical
last_updated: 2026-02-03
---
# PDD — OBSERVER 2.0 (Design Document) v1.2.5

Build date: 2026-02-03

## 1. Design intent

OBSERVER adotta un’impostazione **auditability-first**:

- determinismo e riproducibilità (run_id, transcript, code_fingerprint)
- timing conservativo (no future leak, regola T+1)
- data governance (ticker mapping time-bounded, universe membership)
- output “retail usable” ma verificabile (stars + confidence + drill-down)
- evoluzione *paper-first* verso live, senza compromettere audit e safety.

## 2. Architettura a layer

### 2.1 Entry points (CLI / ops)
- `scripts/sentinel.py`: orchestrazione (migrate/test/run/certify/verify/forecast/status)
- `scripts/news_alpha.py`: NEWS-ALPHA runner (collect/run/status)
- `scripts/execute.py`: execution runner (paper-first)
- `scripts/ops_run_session.py` / `scripts/pack_session.py`: workflow e packaging deterministico
- `scripts/guardian.py`: governance documentale (direct mode)
  - `py scripts/guardian.py gate --wi WI-XXXX --mode normal|close`: gate suite con log in `reports/` (Collector B integrato)
  - `py scripts/guardian.py collect --wi WI-XXXX --mode normal|close`: validazione presenza/emptiness log WI

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

## 4. Contratti di progettazione (policy)

### 4.1 Offline-by-default
Qualunque accesso rete deve essere esplicito (flag/env). Il default è offline.

### 4.2 No future leak
- entry date strettamente successiva al segnale
- disclosure e reason_code per qualunque shift/skip.

### 4.3 Auditability
- `run_id` presente in ogni artefatto importante (DB e filesystem)
- `code_fingerprint` per correlare risultati a snapshot di codice.

## 5. Data layer (DuckDB)

- Owner canonico: `src/db/migrate.py`
- DB locale: `data/sentinel_alpha.db`
- Tabelle chiave: `audit_*`, `recs`, `prices`, `universe_membership`, `ticker_mappings`,
  `execution_orders`, `execution_fills`, `sentiment_cache`, `data_gaps`.

Riferimento: `004_DDT_DATADICTIONARY.md`.

## 6. Risk & Execution: stato e target v1.2.5

### 6.1 Stato as-built (baseline)
- risk gate: cash reserve, max positions, sizing statico (notional cap)
- paper broker: ordine “MARKET” simulato, fill immediato, fees via CostModel
- persistenza: `execution_orders` + `execution_fills`

### 6.2 Target architetturale (v1.2.5)
Obiettivo: passare da “paper dimostrativo” a **paper robusto**.

Componenti mancanti (design):
- **OMS minimal**: lifecycle ordine, idempotenza, reconciliation, position keeping
- **Post-trade risk**: stop/trailing, cooldown, kill-switch
- **Execution realism**: slippage/spread + partial fill simulation (anche se semplificata)
- **TCA**: confronto forecast vs realized e tracking costi effettivi

Interfacce consigliate:
- `BrokerAdapter` (paper/live) con contract uniforme (submit/cancel/poll)
- `OrderIntent` (snapshot del ranking + vincoli applicati) per audit e replay.

## 7. Monitoring & alerting (v1.2.5)

- **Operational**: data gaps, schema mismatch, execution anomalies
- **Model health**: rolling hit-rate / IC proxy, forecast vs realized, drift flags
- **Alerting**: log/DB flags + UI “alert center” (minimo)

## 8. Scenario-driven extensions

Gli scenari e i requisiti aggiuntivi sono descritti in:
- `docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md`

Politica: prima Layer 1 (safety), poi alpha expansion.


---

## 004_DDT_DATADICTIONARY.md

---
doc_id: 004_DDT_DATADICTIONARY
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-30
---
# DATADICTIONARY (DuckDB) — v1.2.5

Build date: 2026-01-30

## Panoramica

OBSERVER / SENTINEL-ALPHA utilizza **DuckDB** come single source of truth locale.  
Il modello dati e’ progettato per:

- riproducibilita’ e auditability (run_id, code_fingerprint, transcript)
- backtest “certification-grade” (no survivorship bias, ticker mappings time-bounded, halts)
- realismo retail (costi transazione, tasse IT, dividendi come estensione)

### Convenzioni generali

- `DATE` e’ usato per la logica di sessione (daily).  
- `TIMESTAMPTZ`/`TIMESTAMP` sono usati per logging e provenance. Quando possibile, usare UTC.
- Le chiavi sono implementate come `PRIMARY KEY` o `UNIQUE` (in alcuni casi DuckDB materializza la chiave come UNIQUE).

### Relazioni logiche (alto livello)

- `audit_runs` 1..N `audit_trades` / `audit_equity` / `audit_signal_decisions` / `data_gaps`
- `dq_runs` 1..N `dq_findings` / `dq_metrics_daily`
- `metadata` 1..N `prices` / `dividends`
- `recs` alimenta `audit_signal_decisions` e, indirettamente, `audit_trades`

---

## DB artifacts e path canonical

- DB DuckDB: `data/sentinel_alpha.db` (default)
- Variabile ambiente (override): `SENTINEL_ALPHA_DB_PATH`
- Snapshot/backup opzionale: `data/sentinel_alpha.zip` (non usato a runtime)

**Principio operativo:** tooling e UI devono usare il path canonical (default o env var) e non hardcodare percorsi assoluti.

## DB surface by phase (vista “delivery”)

| Phase | Tag | Tabelle (principali) |
|---|---|---|
| Phase0 | `PHASE0_FOUNDATION` | `metadata`, `universes`, `universe_membership`, `ticker_mappings` |
| Phase1 | `PHASE1_DATAOPS` | `prices`, `dividends`, `market_halts`, `ticker_halts`, `data_gaps`, `dq_runs`, `dq_findings`, `dq_metrics_daily` |
| Phase2 | `PHASE2_EXECUTION` | `execution_orders`, `execution_fills`, `audit_runs`, `audit_signal_decisions`, `audit_trades`, `audit_equity` |
| Signal plane (supporto) | `PHASE2_SIGNAL` | `recs`, `sentiment_cache`, `momentum_rankings` |

> Nota: le tabelle “audit_*” sono trasversali ma vengono considerate *delivery surface* in Phase2 perché chiudono il loop end-to-end (segnale→decisione→trade→equity).

## DB required matrix (tools/pages — snapshot)

| Entrypoint | Phase | DB | Read/Write | Tabelle principali |
|---|---|---:|---|---|
| `py -m src.tools.db_status` | Phase0 | REQUIRED | R | *introspezione schema* |
| `py -m src.tools.verify_run` / `verify_provenance` | Phase0/2 | REQUIRED | R | `audit_runs`, `audit_*`, `data_gaps` |
| `py -m src.tools.dataops_prices_ingest` | Phase1 | REQUIRED | W | `prices`, `metadata` |
| `py -m src.tools.dataops_sync_halts` / `dataops_import_closures` | Phase1 | REQUIRED | W | `market_halts`, `ticker_halts` |
| `py -m src.tools.dataops_dq_prices` | Phase1 | REQUIRED | W | `dq_runs`, `dq_findings`, `dq_metrics_daily`, `data_gaps` |
| `py scripts/execute.py --paper` | Phase2 | REQUIRED | W | `execution_orders`, `execution_fills`, `audit_*` |
| `pages/11_DataOps_Control_Room.py` | Phase1 | REQUIRED | R/W | `market_halts`, `ticker_halts`, `dq_*` |
| `pages/09_Execution_Log.py` / `pages/10_Monitoring_TCA.py` | Phase2 | REQUIRED | R | `execution_*`, `audit_*` |

---

## `metadata`

Anagrafica strumenti: ticker canonico e attributi di mercato/settore, inclusi flag fiscali (Tobin/FTT) e simboli provider.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico interno (chiave primaria). |
| sector | VARCHAR | YES | Settore economico (granularita’ libera). |
| market | VARCHAR | YES | Etichetta mercato/regione (es. US, EU, ITALY). |
| currency | VARCHAR | YES | Valuta di quotazione (ISO-4217, es. USD, EUR). |
| is_tobin_tax | BOOLEAN | YES | Flag: applica Tobin/FTT (Italia) come costo transazione addizionale. |
| yf_symbol | VARCHAR | YES | Simbolo provider yfinance (se diverso dal ticker canonico). |
| stooq_symbol | VARCHAR | YES | Simbolo provider stooq (se diverso dal ticker canonico). |
| instrument_type | VARCHAR | YES | Classe strumento (EQUITY, ETF, DERIVATIVE, ...). |
| ftt_rate | DOUBLE | YES | Aliquota FTT come frazione del notional (es. 0.001 = 0.10%). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker)

## `prices`

Prezzi giornalieri (barre daily): close (obbligatorio) + open opzionale, con provenance e timestamp di inserimento.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| date | DATE | YES | Data sessione (daily). |
| ticker | VARCHAR | YES | Ticker canonico. |
| price | FLOAT | YES | Prezzo di chiusura (close). |
| open_price | FLOAT | YES | Prezzo di apertura (open), se disponibile. |
| source | VARCHAR | YES | Provenienza riga (legacy/yfinance/stooq/...). |
| fetched_at | TIMESTAMP | YES | Timestamp inserimento/aggiornamento riga. |


### Vincoli (DuckDB)

- UNIQUE: UNIQUE(date, ticker)

## `dividends`

Eventi dividendo per realismo retail (ex-date e pay-date). Nello snapshot lo schema e’ presente; l’applicazione cashflow e’ incrementale.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico. |
| ex_date | DATE | NO | Data ex-dividend. |
| pay_date | DATE | YES | Data pagamento. |
| amount | DOUBLE | YES | Importo dividendo per share/unit. |
| currency | VARCHAR | YES | Valuta importo. |
| source | VARCHAR | YES | Provenienza dato. |
| fetched_at | TIMESTAMP | YES | Timestamp inserimento. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker, ex_date)

## `recs`

Store segnali/raccomandazioni (news/analyst): per data di pubblicazione, ticker, firm e rating, con sentiment score e metadati.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| date | DATE | YES | Data pubblicazione segnale (legacy compatible). |
| ticker | VARCHAR | YES | Ticker del segnale (puo’ essere non canonico: normalizzato/mappato a runtime). |
| firm | VARCHAR | YES | Fonte/firm (es. banca d’affari, provider news). |
| rating | VARCHAR | YES | Rating discreto (BUY/HOLD/DOWNGRADE o analogo). |
| sentiment_score | DOUBLE | YES | Sentiment in [-1,+1] (deterministico, cacheabile). |
| headline | VARCHAR | YES | Titolo/news headline associata al segnale. |
| source_url | VARCHAR | YES | URL sorgente (se disponibile). |
| universe_id | VARCHAR | YES | Universe associato al segnale (ALL/US/EU o custom). |
| published_at | TIMESTAMP | YES | Timestamp pubblicazione (se disponibile). |


### Vincoli (DuckDB)

- UNIQUE: UNIQUE(date, ticker, firm)

## `momentum_rankings`

Ranking momentum giornaliero per ticker (feature/gate) con rendimento periodo e segnali discreti.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| date | DATE | NO | Data calcolo ranking. |
| ticker | VARCHAR | NO | Ticker canonico. |
| monthly_return | FLOAT | YES |  |
| rank_pos | INTEGER | YES |  |
| signal | VARCHAR | YES | Segnale discreto (es. LONG/SHORT/HOLD). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(date, ticker)

## `universes`

Catalogo universi (es. ALL/US/EU) per filtrare segnali e controllare survivorship bias.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| universe_id | VARCHAR | NO | ID universe (chiave primaria). |
| name | VARCHAR | YES | Nome descrittivo. |
| market | VARCHAR | YES | Mercato/regione prevalente (US/EU/MULTI...). |
| description | VARCHAR | YES | Descrizione testuale. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(universe_id)

## `universe_membership`

Membership storica (ticker in universo) con intervalli temporali: essenziale per backtest senza survivorship bias.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| universe_id | VARCHAR | NO | ID universe. |
| ticker | VARCHAR | NO | Ticker canonico. |
| start_date | DATE | NO | Inizio validita’ membership (inclusivo). |
| end_date | DATE | YES | Fine validita’ (inclusivo, NULL=open-ended). |
| source | VARCHAR | YES | Fonte dataset membership. |
| notes | VARCHAR | YES | Note/annotazioni. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(universe_id, ticker, start_date)

## `ticker_mappings`

Mappature alias->canonico time-bounded (corporate actions, cambio simbolo) per evitare mismatch ticker.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| alias_ticker | VARCHAR | NO | Simbolo alias (come appare nel dato grezzo). |
| canonical_ticker | VARCHAR | YES | Simbolo canonico interno. |
| start_date | DATE | NO | Inizio validita’ mapping. |
| end_date | DATE | YES | Fine validita’ mapping (NULL=open-ended). |
| source | VARCHAR | YES | Fonte mapping (manual, provider, corporate actions...). |
| notes | VARCHAR | YES | Note. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(alias_ticker, start_date)

## `ticker_halts`

Halt su singolo ticker: finestra temporale di non-tradabilita’ e reason/provenance.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico. |
| start_date | DATE | NO | Inizio halt. |
| end_date | DATE | YES | Fine halt (NULL=open-ended). |
| reason | VARCHAR | YES | Motivo halt (sospensione, delisting, market maker, ecc.). |
| source | VARCHAR | YES | Fonte informazione. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker, start_date)

## `market_halts`

Halt di mercato/paese (es. circuit breaker, chiusure straordinarie) per execution feasibility.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| market | VARCHAR | NO | Mercato/regione (es. US, EU). |
| start_date | DATE | NO | Inizio halt. |
| end_date | DATE | YES | Fine halt. |
| reason | VARCHAR | YES | Motivo halt (circuit breaker, chiusure, ecc.). |
| source | VARCHAR | YES | Fonte informazione. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(market, start_date)

## `sentiment_cache`

Cache locale deterministica del sentiment (testo normalizzato + hash) per ripetibilita’ e audit.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| text_hash | VARCHAR | NO | Hash del testo normalizzato (chiave primaria). |
| text | VARCHAR | YES | Testo normalizzato (troncato a 2000 char). |
| score | DOUBLE | YES | Sentiment score in [-1,+1]. |
| model | VARCHAR | YES | Modello usato (vader/lexicon). |
| computed_at | TIMESTAMP | YES | Timestamp calcolo (UTC). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(text_hash)

## `data_gaps`

Log operativo di gap/backfill (prezzi/news): include intervalli richiesti, esito, righe inserite e reason_code standardizzato.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| kind | VARCHAR | YES | Tipo gap (prices/news/...). |
| ticker | VARCHAR | YES | Ticker target (se applicabile). |
| start_date | DATE | YES | Inizio finestra da ottenere (normalizzata). |
| end_date | DATE | YES | Fine finestra da ottenere. |
| requested_at | TIMESTAMP | YES | Timestamp richiesta. |
| status | VARCHAR | YES | SUCCESS/FAILED/SKIPPED. |
| provider | VARCHAR | YES | Provider (yfinance/stooq/gdelt/...). |
| message | VARCHAR | YES | Messaggio sintetico esito. |
| rows_inserted | INTEGER | YES | Numero righe inserite. |
| error | VARCHAR | YES | Errore raw (se presente). |
| duration_ms | INTEGER | YES | Durata operazione. |
| run_id | VARCHAR | YES | Run che ha richiesto il backfill (se presente). |
| rows_upserted | INTEGER | YES | Numero righe inserite + aggiornate. |
| reason_code | VARCHAR | YES | Reason code standardizzato (per KPI data quality). |
| requested_start_date | DATE | YES | Inizio richiesto originario (prima di clamp/parse). |
| requested_end_date | DATE | YES | Fine richiesta originaria. |
| obtained_start_date | DATE | YES | Min date effettivamente ottenuta. |
| obtained_end_date | DATE | YES | Max date effettivamente ottenuta. |


### Vincoli (DuckDB)

- (nessun vincolo dichiarato)

## `dq_runs`

Registro esecuzioni Data Quality (PHASE1 DataOps): una riga per run DQ con finestra e stato.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | Identificativo run DQ (chiave primaria). |
| kind | VARCHAR | YES | Tipo DQ (es. DQ_PRICES). |
| started_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp inizio (UTC consigliato). |
| finished_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp fine. |
| asof_date | DATE | YES | Data as-of del controllo (daily). |
| window_days | INTEGER | YES | Finestra lookback in giorni calendario. |
| status | VARCHAR | YES | SUCCESS/FAILED/SKIPPED. |
| notes | VARCHAR | YES | Note sintetiche (parametri + conteggi). |
| error | VARCHAR | YES | Errore raw se FAILED. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id)

## `dq_findings`

Dettaglio findings DQ (PHASE1): missing/stale/invalid, compressi per intervallo.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| finding_id | VARCHAR | NO | ID finding (chiave primaria). |
| run_id | VARCHAR | YES | Run DQ associato. |
| kind | VARCHAR | YES | Tipo finding (PRICE_MISSING/PRICE_STALE/...). |
| severity | VARCHAR | YES | Severità (INFO/WARN/ERROR). |
| market | VARCHAR | YES | Mercato derivato (US/EU/...). |
| ticker | VARCHAR | YES | Ticker canonico. |
| start_date | DATE | YES | Inizio intervallo finding. |
| end_date | DATE | YES | Fine intervallo finding. |
| count | INTEGER | YES | Numero giorni nel finding (best-effort). |
| message | VARCHAR | YES | Messaggio sintetico. |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp creazione record. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(finding_id)

## `dq_metrics_daily`

Metriche aggregate per run DQ (PHASE1) per mercato + metrica.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | Run DQ. |
| asof_date | DATE | NO | Data as-of. |
| market | VARCHAR | NO | Mercato (ALL/US/EU/...). |
| metric | VARCHAR | NO | Nome metrica (tickers, findings, invalid_rows, duration_ms, ...). |
| value | DOUBLE | YES | Valore numerico. |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp inserimento. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id, asof_date, market, metric)

## `audit_runs`

Registro run di audit/certificazione: configurazione, universi, fingerprint del codice e stato esecuzione.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | Identificativo run (chiave primaria, deterministico/UUID-like). |
| started_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp inizio run (UTC consigliato). |
| finished_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp fine run. |
| status | VARCHAR | YES | Stato: RUNNING/SUCCESS/FAILED. |
| universe_id | VARCHAR | YES | Universe testato. |
| holding_period_sessions | INTEGER | YES | Holding period in sessioni (T+N, default definito nella pipeline). |
| config_json | VARCHAR | YES | Configurazione run serializzata (string JSON). |
| code_fingerprint | VARCHAR | YES | Fingerprint del codice (hash) per audit. |
| notes | VARCHAR | YES | Note manuali / annotazioni. |
| error | VARCHAR | YES | Messaggio errore (se FAILED). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id)

## `audit_signal_decisions`

Decision ledger opzionale: traccia segnali eseguiti o scartati (dedup, halt, skip) e date ‘intese’ vs effettive.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| decision_id | VARCHAR | NO | ID decisione (chiave primaria). |
| run_id | VARCHAR | YES | ID run. |
| signal_date | DATE | YES | Data segnale. |
| ticker_original | VARCHAR | YES | Ticker originale. |
| ticker | VARCHAR | YES | Ticker canonico effettivo. |
| firm | VARCHAR | YES | Fonte segnale. |
| rating | VARCHAR | YES | Rating. |
| universe_id | VARCHAR | YES | Universe. |
| intended_buy_date | DATE | YES | Buy date intesa (prima di shift). |
| buy_date | DATE | YES | Buy date effettiva. |
| exec_shift_sessions | INTEGER | YES | Shift buy. |
| intended_sell_date | DATE | YES | Sell date intesa. |
| sell_date | DATE | YES | Sell date effettiva. |
| exit_shift_sessions | INTEGER | YES | Shift sell. |
| decision | VARCHAR | YES | EXECUTED / SKIPPED / DROPPED_DEDUP. |
| skip_reason | VARCHAR | YES | Motivo skip (missing price, halt, policy). |
| halt_reason | VARCHAR | YES | Motivo halt (ticker/market). |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp creazione record. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(decision_id)

## `execution_orders`

Ledger ordini di esecuzione (paper/real): entita’ “ordine” con stato e parametri di submit.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| order_id | VARCHAR | NO | ID ordine (chiave primaria). |
| run_id | VARCHAR | YES | FK logica verso audit_runs.run_id (se presente). |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp creazione ordine (UTC consigliato). |
| ticker | VARCHAR | YES | Ticker canonico target. |
| side | VARCHAR | YES | Lato ordine: BUY/SELL. |
| quantity | DOUBLE | YES | Quantita’ (shares/unit). |
| order_type | VARCHAR | YES | Tipo ordine (MARKET/LIMIT/...). |
| limit_price | DOUBLE | YES | Prezzo limite se LIMIT, altrimenti NULL. |
| status | VARCHAR | YES | Stato ordine (NEW/FILLED/CANCELLED/...). |
| notes | VARCHAR | YES | Note/testo libero. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(order_id)

## `execution_fills`

Ledger fills/eseguiti: ogni fill rappresenta un’esecuzione (anche parziale) di un ordine.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| fill_id | VARCHAR | NO | ID fill (chiave primaria). |
| order_id | VARCHAR | YES | FK logica verso execution_orders.order_id. |
| run_id | VARCHAR | YES | FK logica verso audit_runs.run_id (se presente). |
| filled_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp fill (UTC consigliato). |
| ticker | VARCHAR | YES | Ticker canonico. |
| side | VARCHAR | YES | Lato eseguito: BUY/SELL. |
| quantity | DOUBLE | YES | Quantita’ eseguita. |
| fill_price | DOUBLE | YES | Prezzo di esecuzione. |
| fees | DOUBLE | YES | Commissioni applicate (valuta di conto). |
| notes | VARCHAR | YES | Note/testo libero. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(fill_id)

## `audit_trades`

Trade ledger per run: ogni trade deriva da un segnale, include shift esecutivi, motivi di uscita e performance lorda/netta.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| trade_id | VARCHAR | NO | ID trade (chiave primaria). |
| run_id | VARCHAR | YES | FK logica verso audit_runs.run_id. |
| signal_date | DATE | YES | Data segnale originale (giorno di pubblicazione). |
| buy_date | DATE | YES | Data entrata effettiva (con shift e vincoli). |
| sell_date | DATE | YES | Data uscita effettiva. |
| exit_reason | VARCHAR | YES | Motivo uscita (TARGET/HOLDING_PERIOD/HALT/FALLBACK_LAST_PRICE...). |
| exit_is_fallback | BOOLEAN | YES | Flag: uscita fallback (prezzo last known). |
| ticker | VARCHAR | YES | Ticker effettivo canonico usato per prezzi e membership. |
| firm | VARCHAR | YES | Fonte segnale. |
| rating | VARCHAR | YES | Rating del segnale. |
| market | VARCHAR | YES | Mercato (derivato da metadata o regole). |
| sector | VARCHAR | YES | Settore (derivato da metadata). |
| mom_status | VARCHAR | YES | Esito gate momentum (se applicato). |
| risk_vol | DOUBLE | YES | Volatilita’/proxy rischio usato nella gestione posizione (se presente). |
| is_tobin_tax | BOOLEAN | YES | Flag FTT applicata. |
| sentiment_score | DOUBLE | YES | Sentiment associato al segnale. |
| buy_price | DOUBLE | YES | Prezzo entrata (close o regola scelta). |
| sell_price | DOUBLE | YES | Prezzo uscita. |
| gross_return_pct | DOUBLE | YES | Rendimento lordo (%) pre-costi e pre-tasse. |
| cost_pct | DOUBLE | YES | Costo transazione totale (%) usato nel modello. |
| net_return_pct | DOUBLE | YES | Rendimento netto (%) dopo costi (tasse tracciate altrove). |
| trade_score | DOUBLE | YES | Score del trade (se applicato dal sistema). |
| universe_id | VARCHAR | YES | Universe in cui il trade e’ stato eseguito/valutato. |
| ticker_original | VARCHAR | YES | Ticker originale del segnale (prima di normalize/mapping). |
| instrument_type | VARCHAR | YES | Classe strumento. |
| ftt_pct | DOUBLE | YES | FTT effettiva usata come percentuale del notional. |
| exec_shift_sessions | INTEGER | YES | Shift entrata (sessioni) per vincoli T+1 / prezzi mancanti / halt. |
| exit_shift_sessions | INTEGER | YES | Shift uscita (sessioni). |
| halt_reason | VARCHAR | YES | Motivo di halt (ticker/market) se ha impattato l’esecuzione. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(trade_id)

## `audit_equity`

Equity curve giornaliera per run: equity, cash, investito, numero posizioni e tasse pagate.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | ID run. |
| date | DATE | NO | Data (daily). |
| equity | DOUBLE | YES | Equity totale (cash + posizioni mark-to-market). |
| cash | DOUBLE | YES | Cassa disponibile. |
| invested | DOUBLE | YES | Notional investito (approssimazione). |
| positions | INTEGER | YES | Numero posizioni aperte. |
| tax_paid | DOUBLE | YES | Tasse pagate cumulative o per giorno (dipende dalla pipeline). |
| executed_trades | INTEGER | YES | Numero trade eseguiti nel giorno. |
| closed_trades | INTEGER | YES | Numero trade chiusi nel giorno. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id, date)


---

## 005_TRACEABILITY_MATRIX.md

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


---

## 006_REPO_BOM.md

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


---

## 007_PARAMETER_SNAPSHOT.md

---
doc_id: 007_PARAMETER_SNAPSHOT
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-26
---
# Parameter Snapshot (estratto dal codice) — v1.2.5

Build date: 2026-01-26

Scopo: ridurre divergenze doc-vs-code riportando i **default** e le costanti “contract-like”.

## 1. Cost model (retail realism)

- `src/core/cost_model.py`
  - `CostModel.round_trip_cost_pct = 0.0075` (0.75% round-trip, split entry/exit)

## 2. Tax model (Italia, semplificato)

- `src/core/tax_model.py`
  - `ItalianTaxModel.capital_gains_rate = 0.26`
  - `loss_carry` (zainetto fiscale) gestito in simulazione

## 3. Risk gate (baseline)

- `src/risk/risk_engine.py`
  - `RiskConfig.max_positions = 10`
  - `RiskConfig.cash_reserve_pct = 0.20`
  - `RiskConfig.max_position_pct = 0.20`
  - `RiskConfig.risk_scalar = 1.0`

## 4. Forecast ranking (Wave 6)

- `src/forecast/ranking.py` (Spec: `WAVE6_FORECAST_STARS_RANKING_SPEC.md v0.1`)
  - `N_MIN = 20`
  - `N_CONF = 60`
  - `W_GLOBAL = 0.25`
  - `K_SENT = 0.20`
  - `DEFAULT_TOP_N = 25`
  - `DEFAULT_EXCLUDE_EXIT_REASON = "FALLBACK_LAST_PRICE"`

## 5. NEWS-ALPHA deterministic sentiment

- `src/news_alpha/sentiment.py`
  - `MODEL = "lexicon-v1"`
  - scoring: `(pos - neg) / (pos + neg)` in [-1, +1] su token `[A-Za-z]+`

## 6. Execution (paper)

- `src/execution/paper_broker.py`
  - `starting_cash` default: 100000.0
  - order type: `MARKET` (paper), fill immediato, fees via `CostModel.entry_cost()`


---

## 008_EVIDENCE_PACK.md

doc_id: 008_EVIDENCE_PACK
docset_version: 1.2.5
status: canonical
last_updated: 2026-02-03
---
# Evidence Pack — v1.2.5

Build date: 2026-02-03

Questo documento elenca comandi “verificabili” per dimostrare che lo snapshot è eseguibile e coerente.

> Nota: su Windows/PowerShell usare `py` invece di `python`.

## 1. Sanity checks

- Test suite (baseline): `py -m pytest`
- Test suite (strict deprecation gate): `py -m pytest -q -W error::DeprecationWarning`
- Stato GUARDIAN: `py scripts/guardian.py status`
- Lint docset: `py scripts/guardian.py lint`

## 2. Data layer (DuckDB)

- Migrazione schema: `py -m src.db.migrate --db data/sentinel_alpha.db`

## 3. Pipeline sentinel (audit/backtest)

- Help runner: `py scripts/sentinel.py --help`
- Status: `py scripts/sentinel.py status`
- Certify (offline default): `py scripts/sentinel.py certify`

Artefatti attesi:
- record in `audit_runs`, `audit_trades`, `audit_equity`
- transcript/summary in `reports/`

## 4. NEWS-ALPHA

- Help runner: `py scripts/news_alpha.py --help`
- Status: `py scripts/news_alpha.py status`
- Run (offline, se configurato con fixtures): `py scripts/news_alpha.py run`

Artefatti attesi:
- `sentiment_cache` popolata
- report/JSONL in `reports/news_alpha/` (se abilitato)

## 5. Forecast ranking (Wave 6)

- Help: `py -m src.forecast.ranking --help` (se esposto) oppure via sentinel
- Generate ranking: `py scripts/sentinel.py forecast --universe ALL --top-n 25`

Artefatti attesi:
- output ranking deterministico + stars
- record/report associati a `run_id`

## 6. Execution (paper-first)

- Help: `py scripts/execute.py --help`
- Paper execution: `py scripts/execute.py --top-n 10 --starting-cash 100000`

Artefatti attesi:
- tabelle `execution_orders` e `execution_fills` aggiornate
- report execution (se presente) e tracciabilità via `run_id`

## 7. Packaging sessione

- `py scripts/pack_session.py --help`
- `py scripts/ops_run_session.py --help`

## 8. Docset governance

- Sync canonici: `py scripts/guardian.py sync --clean`
- Derive brief: `py scripts/guardian.py derive`

### 8.1 Gate suite per Work Item (one-command)

Il repo supporta una gate suite "per WI" con logging standardizzato in `reports/`.

- **Normal (7 log)**: `py scripts/guardian.py gate --wi WI-XXXX --mode normal`
- **Close (4 log)**: `py scripts/guardian.py gate --wi WI-XXXX --mode close`

Validazione log (solo check, nessuna esecuzione):
- `py scripts/guardian.py collect --wi WI-XXXX --mode normal`
- `py scripts/guardian.py collect --wi WI-XXXX --mode close`


## WI Discipline — Gate + Collector (strict)

- `py scripts/guardian.py gate --wi WI-XXXX --mode normal|close --write-collect-log`
  - Collector B è eseguito a fine gate con `--profile hardfail --fail-on-hits` (default).
- `py scripts/guardian.py collect --wi WI-XXXX --mode normal|close --profile deprec --fail-on-hits`
  - Profilo `deprec` per rendere bloccanti warning legacy (se necessario).


---

## 009_GAP_REGISTER.md

---
doc_id: 009_GAP_REGISTER
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-26
---

## Indice gap (ID stabili)

This index provides **stable identifiers** used by:
- `docs/010_MODULE_REGISTRY.md` (Derived gaps column)
- `docs/011_GAP_DERIVATION_MATRIX.md` (root gaps)
- MkDocs navigation

| Gap ID | Area | Title |
|---|---|---|
| GAP-OMS | Execution | Order Management System (OMS) |
| GAP-BROKER-ADAPTER | Execution | Live broker adapter + kill-switch |
| GAP-EXEC-LOG | Execution/Monitoring | Stable execution log (orders/fills lifecycle) |
| GAP-RISK-HARDEN | Risk | Hardened Risk Engine (dynamic stops, limits, kill-switch policy) |
| GAP-GUARDRAILS | Risk/Ops | Behavioral guardrails (discipline mode, cooling-off) |
| GAP-ALERTING | Monitoring/Ops | Alerting & notification channels |
| GAP-DRIFT | Monitoring | Drift detection + model monitoring |
| GAP-CA-COLLECTOR | Data | Corporate actions collector (splits/dividends/events) |
| GAP-MACRO-LAYER | Data/Signal | Macro data layer + regime detection |
| GAP-PAIRS-ENGINE | Signal/Execution | Pairs trading engine (selection, z-score, neutrality) |

## Dettagli gap (per ID)

### GAP-OMS — Order Management System (OMS)
- **Driver**: missing order state machine (NEW→SUBMITTED→FILLED/CANCELLED/REJECTED) + replay-safe reconciliation.
- **Blocks**: broker adapter, trade ticket, reliable alerts, post-trade attribution.
- **Acceptance (minima)**: persistent state; deterministic IDs; validated transitions; replay-safe.

### GAP-BROKER-ADAPTER — Live broker adapter + kill-switch
- **Driver**: no real broker interface + no hard kill-switch boundary.
- **Blocks**: LIVE-GRADE; real fills; real-time exposure control.
- **Acceptance (minima)**: adapter interface; sandbox; emergency stop; full audit.

### GAP-EXEC-LOG — Stable execution log
- **Driver**: orders/fills logging not yet a stable contract for monitoring/analytics.
- **Blocks**: TCA, slippage calibration, attribution, drift baselines.
- **Acceptance (minima)**: immutable fills; consistent order↔fill↔portfolio link; latency/fees captured.

### GAP-RISK-HARDEN — Hardened Risk Engine
- **Driver**: current checks are basic; not sufficient for safe paper/live.
- **Blocks**: guardrails, dynamic stops, concentration, kill-switch policy.
- **Acceptance (minima)**: pre+post trade; stop framework; global limits; tested edge cases.

### GAP-GUARDRAILS — Behavioral guardrails
- **Driver**: no discipline-mode / cooling-off / override policy.
- **Blocks**: safe retail ops; reduces user-error failure mode.
- **Acceptance (minima)**: cooling-off after stop; max overrides; hard blocks.

### GAP-ALERTING — Alerting & notifications
- **Driver**: no alert lifecycle (create→route→ack→close).
- **Blocks**: sustainable ops; incident response; user trust.
- **Acceptance (minima)**: rules; channels (local + email/webhook); ack logging.

### GAP-DRIFT — Drift detection + model monitoring
- **Driver**: missing KPIs/thresholds and baselines to detect drift/decay.
- **Blocks**: safe signal evolution; early warning for alpha decay.
- **Acceptance (minima)**: baselines; thresholds; periodic evaluation; alert integration.

### GAP-CA-COLLECTOR — Corporate actions collector
- **Driver**: no automated CA ingestion/normalization; timing errors likely.
- **Blocks**: event-driven strategies; correct price adjustments.
- **Acceptance (minima)**: collector; mapping; timing rules; CA audit entries.

### GAP-MACRO-LAYER — Macro data layer + regime detection
- **Driver**: missing macro inputs and regime classifier.
- **Blocks**: tactical rotation; regime-aware weighting.
- **Acceptance (minima)**: macro ingest; features; regime labels; backfill+validation.

### GAP-PAIRS-ENGINE — Pairs trading engine
- **Driver**: missing pair selection, spread monitoring, neutrality enforcement.
- **Blocks**: scenario 5.
- **Acceptance (minima)**: selection; z-score pipeline; breakdown detection; execution hooks.


# GAP Register — v1.2.5 (as-built vs target)

Build date: 2026-01-26

## 1. Scopo

Registrare in modo auditabile:
- cosa è già implementato (as-built)
- cosa è parziale/basilare
- cosa manca per conformità v1.2.5 e per scenari operativi

Riferimento scenari: `docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md`

## 2. Priorità e codifica

- **P0 (bloccante)**: impedisce paper robusto / qualsiasi live readiness
- **P1 (alta)**: necessario per sostenibilità e qualità retail
- **P2 (media)**: differenziazione / alpha expansion
- **P3 (nice-to-have)**

## 3. Gap principali per layer

### Layer 1 — Risk & Execution (P0/P1)

| Gap | Stato as-built | Impatto | Target (milestone) |
|---|---|---|---|
| RiskEngine evoluto (stop/trailing/kill-switch/cooldown) | PARZIALE (gate statico) | P0 | M1 |
| OMS lifecycle + posizione/PNL accounting | ASSENTE (solo orders/fills) | P0 | M1 |
| Slippage/spread model realistico + TCA | ASSENTE | P1 | M1 |
| Reconciliation + idempotenza ordini/fills | ASSENTE | P1 | M1 |
| BrokerAdapter interface (paper/live) | PARZIALE (paper only) | P1 | M1→M2 |

### Layer 2 — Alpha enhancement (P2)

| Gap | Scenario | Stato as-built | Target |
|---|---:|---|---|
| Factor library estesa (value/quality) | 2 | ASSENTE | M2 |
| Dynamic weighting regime-aware | 2,4 | ASSENTE | M2/M4 |
| Corporate actions collector + event engine | 3 | ASSENTE | M3 |
| Macro data layer + regime detection | 4 | ASSENTE | M4 |
| Pairs selection/monitoring + market-neutral exec | 5 | ASSENTE | M4 |

### Layer 3 — Feedback & Monitoring (P1)

| Gap | Stato as-built | Target |
|---|---|---|
| Model monitoring rolling + alert thresholds | BASICO | M1/M2 |
| Drift detection (features/target) | ASSENTE | M2/M3 |
| Alert center (UI + notifiche) | BASICO | M1 |

### Layer 4 — UI/UX operativa (P2)

| Gap | Stato as-built | Target |
|---|---|---|
| Trade ticket / execute workflow guidato | BASICO | M1 |
| What-if analysis (risk preview) | ASSENTE | M1/M2 |
| One-click execution con conferme e guardrails | ASSENTE | M1 |

## 4. Note di realismo

- Le stime FTE sono sensibili a: broker scelto, qualità fonti dati (corporate actions/macro), e profondità monitoring richiesta.
- Il “paper trading funzionante” è più vicino (perché paper broker e gate esistono), ma il salto a *paper robusto* richiede OMS + post-trade + monitoring.


---

## 010_MODULE_REGISTRY.md

---
docset_version: 1.2.5
last_updated: 2026-02-03
status: support
---

# 010 — Registro Moduli (as-built + target) — v1.2.5

## Scopo
Definire i **moduli** di OBSERVER come entità governabili e quasi-finite, distinguendo:

- **as-built**: cosa esiste oggi nel codice ed è eseguibile (RUN-GRADE)
- **target**: cosa manca per paper/live in modo sicuro (PAPER-GRADE / LIVE-GRADE)

Questo registro fa da ponte tra:
- `docs/005_TRACEABILITY_MATRIX.md` (repo → documentazione)
- `docs/009_GAP_REGISTER.md` (gap / backlog con acceptance criteria)
- `docs/008_EVIDENCE_PACK.md` (runbook: come eseguire e verificare)

## Livelli di maturità
- **RUN-GRADE**: esecuzione ripetibile, idempotenza ragionevole, logging minimo, smoke test.
- **PAPER-GRADE**: RUN-GRADE + semantica paper trading coerente, audit trail, report minimi.
- **LIVE-GRADE**: PAPER-GRADE + OMS + broker adapter reale, risk controls hard, alerting, kill-switch.

## Definition of Done minima (per dichiarare un modulo RUN-GRADE)
1. Entrypoint stabile (CLI o funzione) e parametri documentati
2. Contract di output (tabelle/artefatti) e invarianti principali
3. Test minimi (unit + smoke integration)
4. Osservabilità (log + contatori)
5. 1 riga in `005_TRACEABILITY_MATRIX.md` + 1 paragrafo in `008_EVIDENCE_PACK.md`

## Indice moduli (cliccabile)
- [MOD-INFRA-BASE](#mod-infra-base)
- [MOD-GUARDIAN-DOCOPS](#mod-guardian-docops)
- [MOD-DB-SCHEMA](#mod-db-schema)
- [MOD-DATAOPS](#mod-dataops)
- [MOD-OPS-RUN-SESSION](#mod-ops-run-session)
- [MOD-SENTINEL-OPS](#mod-sentinel-ops)
- [MOD-NEWS-ALPHA](#mod-news-alpha)
- [MOD-FORECAST-RANK](#mod-forecast-rank)
- [MOD-AUDIT](#mod-audit)
- [MOD-RISK-GATE](#mod-risk-gate)
- [MOD-EXEC-PAPER](#mod-exec-paper)
- [MOD-OMS](#mod-oms)
- [MOD-BROKER-ADAPTER](#mod-broker-adapter)
- [MOD-BEHAVIORAL-GUARDRAILS](#mod-behavioral-guardrails)
- [MOD-MONITOR-TCA](#mod-monitor-tca)
- [MOD-ALERTING](#mod-alerting)
- [MOD-DRIFT-MONITOR](#mod-drift-monitor)
- [MOD-UI-CONSOLE](#mod-ui-console)

## Moduli — schede sintetiche

> Nota: “Gap derivati” usa gli ID `GAP-*` definiti in `docs/009_GAP_REGISTER.md`.

### MOD-INFRA-BASE
- **Dominio**: Infrastruttura (prerequisiti comuni)
- **Phase**: PHASE0_FOUNDATION
- **Livello**: RUN-GRADE
- **Entrypoint**: `py scripts/sentinel.py status` / `verify`
- **Codice**: `scripts/sentinel.py`, `src/config/*`
- **Output**: report ambiente/config
- **Gate minimi**: smoke + validazione config
- **Gap derivati**: se instabile → drift su tutti i run

### MOD-DB-SCHEMA
- **Dominio**: Infrastruttura (DB)
- **Phase**: PHASE0_FOUNDATION
- **Livello**: RUN-GRADE
- **Entrypoint**: `py scripts/sentinel.py migrate`
- **Codice**: `src/phase0/db/migrate.py` (shim: `src/db/migrate.py`)
- **Output**: schema tabelle core
- **Gate minimi**: migrate + schema checks
- **Gap derivati**: blocca ingestione/segnali/esecuzione se schema non stabile


### MOD-DATAOPS
- **Dominio**: DataOps (stabilità dati prezzi)
- **Phase**: PHASE1_DATAOPS
- **Livello**: RUN-GRADE
- **Entrypoint**: 
  - `py -m src.tools.dataops_status`
  - `py -m src.tools.dataops_prices_ingest`
  - `py -m src.tools.dataops_sync_halts`
  - `py -m src.tools.dataops_import_closures`
  - `py -m src.tools.dataops_dq_prices`
- **Codice**: `src/phase0/dataops/*` (shim: `src/dataops/*`), `src/phase0/tools/dataops_*.py` (shim: `src/tools/dataops_*.py`), `config/dataops/*`, `src/phase2/pages/11_DataOps_Control_Room.py` (shim: `pages/11_DataOps_Control_Room.py`)
- **Output**: `market_halts`, `ticker_halts`, `data_gaps`, `dq_runs`, `dq_findings`, `dq_metrics_daily`
- **Gate minimi**: schema migrate + ingest offline + DQ halt-aware + test minimi
- **Gap derivati**: blocca esecuzione/monitoring se dati prezzi instabili (dipende da `GAP-DATAOPS-HARDEN` se introdotto)

### MOD-OPS-RUN-SESSION
- **Dominio**: Infrastruttura (disciplina run/session)
- **Phase**: PHASE0_FOUNDATION
- **Livello**: RUN-GRADE
- **Entrypoint**: `py scripts/ops_run_session.py`
- **Codice**: `scripts/ops_run_session.py`
- **Output**: run_id/session packaging
- **Gate minimi**: dry-run
- **Gap derivati**: riduce provenance/audit se assente

### MOD-SENTINEL-OPS
- **Dominio**: Orchestrazione
- **Phase**: PHASE0_FOUNDATION
- **Livello**: RUN-GRADE
- **Entrypoint**: `py scripts/sentinel.py run|certify|status|verify`
- **Codice**: `scripts/sentinel.py`
- **Output**: `reports/*` + DB
- **Gate minimi**: `py scripts/sentinel.py test`
- **Gap derivati**: aumenta errore umano se non c’è “one-command ops”

### MOD-GUARDIAN-DOCOPS
- **Dominio**: Governance / Tooling operativo
- **Phase**: PHASE0_FOUNDATION
- **Livello**: RUN-GRADE
- **Entrypoint**:
  - `py scripts/guardian.py gate --wi WI-XXXX --mode normal|close`
  - `py scripts/guardian.py collect --wi WI-XXXX --mode normal|close`
- **Codice**: `scripts/guardian.py`, `scripts/wi_gate_runner.py`, `scripts/wi_log_collector.py`
- **Output**: log standardizzati in `reports/` (`*_WI-XXXX.log`) + summary `wi_gate_*`, `wi_collect_*`
- **Gate minimi**: `py scripts/guardian.py gate --wi WI-XXXX --mode normal` (include strict deprecation gate)
- **Gap derivati**: senza disciplina logs → evidence fragile / drift non osservabile

### MOD-NEWS-ALPHA
- **Dominio**: Data+Signal
- **Phase**: PHASE2_SIGNAL
- **Livello**: RUN-GRADE
- **Entrypoint**: `py scripts/news_alpha.py collect|run|status`
- **Codice**: `src/news_alpha/*` + runner
- **Output**: `recs`, `sentiment_cache`
- **Gate minimi**: `--online` esplicito + audit rows
- **Gap derivati**: degradano segnali/forecast se la freshness è scarsa

### MOD-FORECAST-RANK
- **Dominio**: Signal plane
- **Phase**: PHASE2_SIGNAL
- **Livello**: RUN-GRADE
- **Entrypoint**: (runner/pipeline)
- **Codice**: `src/forecast/ranking.py`
- **Output**: ranking (+ audit)
- **Gate minimi**: determinismo as-of-date
- **Gap derivati**: esecuzione non validabile senza ranking deterministico

### MOD-AUDIT
- **Dominio**: Governance
- **Phase**: PHASE0_FOUNDATION
- **Livello**: RUN-GRADE
- **Entrypoint**: (invocato da pipeline)
- **Codice**: `src/phase0/core/audit_engine.py` (shim: `src/core/audit_engine.py`), `src/phase0/db/audit_store.py` (shim: `src/db/audit_store.py`), `src/analyst_auditor.py`
- **Output**: `audit_*`
- **Gate minimi**: provenance/verify_run
- **Gap derivati**: post-mortem/monitoring meno affidabili

### MOD-RISK-GATE
- **Dominio**: Risk
- **Phase**: PHASE2_EXECUTION
- **Livello**: RUN-GRADE (basico)
- **Entrypoint**: (invocato da execution)
- **Codice**: `src/risk/risk_engine.py`
- **Output**: decisioni risk
- **Gate minimi**: unit tests
- **Gap derivati**: senza hardening → `GAP-RISK-HARDEN`, `GAP-GUARDRAILS`

### MOD-EXEC-PAPER
- **Dominio**: Execution
- **Phase**: PHASE2_EXECUTION
- **Livello**: PAPER-GRADE (baseline)
- **Entrypoint**: `py scripts/execute.py --paper`
- **Codice**: `src/execution/paper_broker.py`
- **Output**: `execution_orders`, `execution_fills`
- **Gate minimi**: test paper execution
- **Gap derivati**: monitoring/attribution dipendono da `GAP-EXEC-LOG`

### MOD-OMS
- **Dominio**: Execution
- **Phase**: PHASE2_EXECUTION
- **Livello**: TARGET (P0)
- **Entrypoint**: (da creare)
- **Codice**: `src/execution/oms/*`
- **Output**: order lifecycle/state machine
- **Gate minimi**: invarianti OMS
- **Gap derivati**: **root** `GAP-OMS` → sblocca alerting, trade ticket, reconciliation

### MOD-BROKER-ADAPTER
- **Dominio**: Execution
- **Phase**: PHASE2_EXECUTION
- **Livello**: TARGET (P0)
- **Entrypoint**: (da creare)
- **Codice**: `src/execution/broker/*`
- **Output**: fills reali + kill-switch boundary
- **Gate minimi**: kill-switch test
- **Gap derivati**: `GAP-BROKER-ADAPTER` blocca LIVE-GRADE

### MOD-BEHAVIORAL-GUARDRAILS
- **Dominio**: Risk/Ops
- **Phase**: PHASE2_EXECUTION
- **Livello**: TARGET (P0)
- **Entrypoint**: (da creare)
- **Codice**: `src/risk/guardrails/*`
- **Output**: policy actions
- **Gate minimi**: hard blocks
- **Gap derivati**: `GAP-GUARDRAILS`

### MOD-MONITOR-TCA
- **Dominio**: Monitoring
- **Phase**: PHASE2_EXECUTION
- **Livello**: RUN-GRADE
- **Entrypoint**: `py -m src.monitoring ...`
- **Codice**: `src/monitoring/tca_report.py`
- **Output**: report TCA
- **Gate minimi**: unit tests
- **Gap derivati**: serve `GAP-EXEC-LOG` stabile

### MOD-ALERTING
- **Dominio**: Monitoring/Ops
- **Phase**: PHASE2_EXECUTION
- **Livello**: TARGET (P1)
- **Entrypoint**: (da creare)
- **Codice**: `src/phase0/core/alert_lifecycle.py` (shim: `src/core/alert_lifecycle.py`) (base)
- **Output**: notifiche
- **Gate minimi**: alert rules
- **Gap derivati**: `GAP-ALERTING`

### MOD-DRIFT-MONITOR
- **Dominio**: Monitoring
- **Phase**: PHASE2_EXECUTION
- **Livello**: TARGET (P1)
- **Entrypoint**: (da creare)
- **Codice**: `src/monitoring/*`
- **Output**: drift KPIs
- **Gate minimi**: thresholds
- **Gap derivati**: `GAP-DRIFT` (dipende da `GAP-EXEC-LOG`)

### MOD-UI-CONSOLE
- **Dominio**: UI
- **Phase**: PHASE_UI
- **Livello**: RUN-GRADE
- **Entrypoint**: (streamlit)
- **Codice**: `src/phase2/pages/*.py` (shim: `pages/*.py`)
- **Output**: —
- **Gate minimi**: smoke manuale
- **Gap derivati**: non bloccante, ma riduce costi operativi


### MOD-WI-COLLECTOR-STRICT

- Scope: tooling
- Entry: `py scripts/guardian.py collect` (profiles + strict-hits)
- Files: `scripts/wi_log_collector.py`

### MOD-WI-GATE-RUNNER-STRICT

- Scope: tooling
- Entry: `py scripts/guardian.py gate` (default collector strict-hits)
- Files: `scripts/wi_gate_runner.py`


---

## 012_REFACTOR_PLAN_VIRTUAL.md

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
- `reports/pytest_<WI>.log`
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
- `reports/pytest_<WI>.log`

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

Per ogni WI, questi file sono attesi (minimo):

- `reports/pytest_<WI>.log`
- `reports/guardian_lint_<WI>.log`

Se applicabile (raccomandati):

- `reports/build_master_md_<WI>.log` (solo se il WI aggiorna derivati/canonici)
- `reports/import_smoke_<WI>.log`
- `reports/compileall_<WI>.log`
- `reports/guardian_sync_<WI>.log`
- `reports/guardian_derive_<WI>.log`

<!-- WI-0114:BEGIN -->
### Gate protocol + expected logs snapshot (WI-0114) — auto
- Report: `reports/WI-0114_gates.md`
- Naming: `reports/pytest_<WI>.log`, `reports/guardian_lint_<WI>.log`, `reports/build_master_md_<WI>.log` (if used)
- Planning-only in WI-0114: no changes to `src/**` or `test/**`.
<!-- WI-0114:END -->


---

# Technical Specs (docs/specs)

## specs\AUDIT_LIFECYCLE_SPEC.md

# AUDIT_LIFECYCLE_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Formalizzare gli stati lifecycle e il decision ledger, in modo che:

- la UI possa rappresentare correttamente stati e transizioni
- i motivi di esclusione siano espliciti (auditability)
- le “eccezioni” (fallback, halt, right-censor) siano disclosure-first

## Stati (concettuali)

### Stati pre-trade (eligibility)
- **CANDIDATE**: segnale presente in `recs` per la data as-of.
- **ELIGIBLE**: passa normalize + ticker_mappings + universe_membership.
- **ENTERABLE**: esiste `intended_buy_date` (prezzo disponibile dopo il segnale).
- **WAITLIST**: temporaneamente non enterable per halt o gap dati (policy-dependent).
- **DROPPED**: scartato (right-censored, missing prices, fuori universo, dedup).

### Stati trade (execution)
- **EXECUTED**: trade creato in `audit_trades`.
- **CLOSED**: trade chiuso con `sell_date` e `exit_reason`.
- **FALLBACK_EXIT**: uscita con prezzo fallback (disclosure).

## Decision ledger

Tabella: `audit_signal_decisions`

Minimi campi richiesti:
- ticker_original, ticker, firm, rating, universe_id, signal_date
- intended_buy_date vs buy_date (+ exec_shift_sessions)
- intended_sell_date vs sell_date (+ exit_shift_sessions)
- decision (EXECUTED/SKIPPED/DROPPED_DEDUP)
- skip_reason e/o halt_reason

## Regole di disclosure

- Ogni skip deve avere motivazione classificabile (skip_reason/reason_code).
- Ogni fallback deve essere marcato come tale e idealmente escluso dalla calibrazione forecast (default exclude_exit_reason).


---

## specs\NEWS_ALPHA_SPEC.md

# NEWS_ALPHA_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Definire la lane NEWS-ALPHA:

- raccolta (RSS/History) con posture online guardata
- scoring sentiment deterministico
- dedup e aggregazione
- persistenza in DuckDB (recs + sentiment_cache)

Runner: `scripts/news_alpha.py`

## Postura online (guardrail)

Azioni online richiedono **ENTRAMBI**:
- `--online`
- `NEWS_ALPHA_ALLOW_ONLINE=1` oppure `--allow-online`

Motivazione: evitare cambi non deterministici e rispettare l’approccio offline-by-default.

## Pipeline RSS (collect)

Input:
- intervallo date (date-from, date-to)
- query window `when-days`
- eventuale allowlist domini

Output:
- raw RSS XML (se online) in `reports/news_alpha/raw/rss`
- fixtures JSONL in `reports/news_alpha/collector/collector_<ts>.jsonl`
- stats JSON con conteggi e qualità

Gate opzionale:
- `--strict-dq`: fallisce se zero items “kept”.

## Pipeline run (fixtures -> DuckDB)

Input:
- fixtures JSONL
- intervallo date

Azioni:
- scoring + dedup
- mapping a ticker
- calcolo rating discreto da score medio:

  - BUY se score >= 0.20
  - DOWNGRADE se score <= -0.20
  - HOLD altrimenti

Output:
- write in `recs` (firm lane news-alpha) e `sentiment_cache`
- rejects JSONL opzionale con motivazione
- log file opzionale (plain o JSONL)

## History lane (GDELT)

Il runner include comandi `history` (download/profile/fixtures) per alimentare dataset storici,
sempre con guardrail online.


---

## specs\SENTINEL_RUNNER_SPEC.md

# SENTINEL_RUNNER_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Definire il contratto operativo del runner `scripts/sentinel.py`:

- CLI minimale e stabile
- run_id, transcript e posture offline/online
- integrazione con schema owner e tool di verifica

## Comandi supportati

- `migrate`: crea/aggiorna schema DuckDB e seed universi base
- `test`: esegue suite test
- `run`: esegue audit run (operativo)
- `certify`: esegue audit run in postura “certification-grade” (offline-by-default)
- `verify`: verifica un run_id (consistenza e policy)
- `forecast`: genera ranking a stelle (Wave 6)
- `status`: summary DB e ambiente

## Run ID

- Variabile ambiente: `SENTINEL_RUN_ID`
- Se assente e il comando e’ in {"run","certify","verify"}, il runner genera un run_id e lo preserva.

## Transcript

- `run` -> `reports/RUN_TRANSCRIPT_<run_id>.txt`
- `certify` -> `reports/CERTIFY_TRANSCRIPT_<run_id>.txt`
- Transcripts sono best-effort: non bloccano l’esecuzione.

## Offline/Online posture

- Flag:
  - `--offline` forza offline
  - `--online` abilita online backfill
- Precedenza:
  1) `--online`
  2) `--offline` / `--no-backfill`
  3) `certify` default offline

Variabili ambiente rilevanti:
- `SENTINEL_ALLOW_ONLINE_BACKFILL`
- `SENTINEL_OFFLINE`
- `SENTINEL_PRICE_PROVIDER_ORDER`
- `SENTINEL_DISABLE_YFINANCE` (default 1)

## Disclosure defaults (retail)

Il runner imposta:
- `SENTINEL_DIVIDEND_POLICY = B`
- `SENTINEL_TIMING_MODE = T_PLUS_1`

Nota: nello snapshot questi switch sono *disclosure* (registrati nei report) e non necessariamente alterano tutta la logica economica.


---

## specs\WAVE6_FORECAST_STARS_RANKING_SPEC.md

# WAVE6_FORECAST_STARS_RANKING_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Definire una procedura deterministica per produrre:

- forecast_return_pct (proxy rendimento atteso)
- confidence (affidabilita’ della stima)
- stars (1..5) come sintesi retail
- ranking deterministico (tie-break stabili)

Questa spec e’ implementata in `src/forecast/ranking.py`.

## Input

- Tabelle DuckDB:
  - `recs` (segnali con firm, rating, sentiment_score, headline, url)
  - `audit_trades` (storico trade per calibrazione)
  - `prices` (per determinare enterability / buy_date)
  - `universe_membership`, `ticker_mappings` (eligibility)

- Parametri (dal codice):
  - N_MIN = 20
  - N_CONF = 60
  - W_GLOBAL = 0.25
  - K_SENT = 0.20
  - DEFAULT_TOP_N = 25
  - DEFAULT_EXCLUDE_EXIT_REASON = FALLBACK_LAST_PRICE

## Output

Un dict JSON-serializzabile con:

- metadata: spec_name, spec_version, asof_date, universe_id, top_n
- diagnostics: candidates_total, enterable_total, dropped_missing_prices, dropped_right_censored, calibration_global_n, calibration_global_mean_return_pct
- rows: lista segnali con forecast/confidence/stars e breakdown
- by_firm: aggregazioni per firm

## Algoritmo (passi)

### Step 0 - Determine as-of date
- asof_date = max(recs.date) nel perimetro `universe_id` (ALL o filtro).

### Step 1 - Load candidate signals
- filtrare recs in data = asof_date
- normalizzare ticker (`normalize_ticker_sql`)
- applicare `ticker_mappings` time-bounded
- join con `universe_membership` time-bounded (survivorship control)
- calcolare `intended_buy_date = MIN(prices.date) > signal_date`
- segnali senza intended_buy_date sono “non enterable” (right-censored o missing).

### Step 2 - Load calibration stats (audit_trades)
- usare trade storici con `signal_date < asof_date`
- escludere (default) `exit_reason = DEFAULT_EXCLUDE_EXIT_REASON` per evitare contaminazione da fallback
- calcolare:
  - bucket_stats per (firm,rating): n, mean_return_pct, stdev_return_pct, last_signal_date
  - firm_stats per firm: n, mean_return_pct
  - global_stats: n, mean_return_pct

### Step 3 - Shrinkage (robustezza piccoli campioni)
Per ogni bucket (firm,rating):

- se n_bucket >= N_MIN: shrunk = bucket_mean
- altrimenti:
  - alpha = n_bucket / N_MIN
  - blend verso firm_mean: bucket_mean*alpha + firm_mean*(1-alpha)
  - blend verso global_mean con prior_weight = max(W_GLOBAL, 1-alpha)

### Step 4 - Sentiment adjustment
- clamp sentiment_score in [-1,+1]
- sent_adj = sentiment_score * K_SENT

### Step 5 - Forecast e confidence
- forecast_return_pct = shrunk_return_pct + sent_adj
- confidence = min(1, n_bucket / N_CONF)

**Fallback**: se global_n <= 0 (nessun trade storico)
- shrunk_return_pct = 0
- confidence = 0
- sent_adj = sentiment_score * 0.50
- forecast = sent_adj

### Step 6 - Ranking e stars
- ordinare per:
  1) forecast_return_pct desc
  2) confidence desc
  3) rating asc (tie-break deterministico)
  4) firm asc
  5) ticker_effective asc
- assegnare stars per percentile:
  - 5 stelle: top 10%
  - 4 stelle: successivo 20%
  - 3 stelle: successivo 40%
  - 2 stelle: successivo 20%
  - 1 stella: bottom 10%

## Disclosure / retail notes

- Forecast non e’ una “promessa”: e’ una metrica comparativa basata su storico e sentiment.
- Confidence e’ esplicita per evitare falsa precisione su bucket piccoli.


---
