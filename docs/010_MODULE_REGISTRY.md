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
  - `py scripts/guardian.py docs-check --mode warn|hard`
- **Codice**: `scripts/guardian.py`, `scripts/wi_gate_runner.py`, `scripts/wi_log_collector.py`, `scripts/doc_integrity_check.py`
- **Output**: log standardizzati in `reports/` (`*_WI-XXXX.log`) + summary `wi_gate_*`, `wi_collect_*` + docs log `docs_check_*`
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
