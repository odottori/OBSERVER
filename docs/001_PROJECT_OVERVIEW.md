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
