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
