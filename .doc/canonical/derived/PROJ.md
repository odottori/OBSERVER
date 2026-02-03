# PROJ — Operational Project Brief

> GENERATED FILE — DO NOT EDIT  
> Source of truth: `./docs/`  
> Generated: 2026-02-03T15:25:19Z  
> Fingerprint: ea89b52c938441b1

## Sources
- `docs/001_PROJECT_OVERVIEW.md`
- `docs/002_PDR_OBSERVER.md`
- `docs/009_GAP_REGISTER.md`

---
## 1. In una frase

**OBSERVER** è un sistema *offline-by-default* che raccoglie segnali (news/analyst), li sottopone a gate di qualità/provenance, esegue audit/backtest conservativi (no future leak) e produce **ranking deterministici** (stars + confidence) con evidenze riproducibili.


## 2. Il problema che risolve (retail avanzato)

- Backtest non auditabile (leakage, universi non controllati, risultati non riproducibili).
- Dati “sporchi” (ticker mapping, prezzi mancanti, sospensioni, corporate actions).
- Segnali non comparabili (fonti diverse senza calibrazione/confidence).
- Operatività opaca (mancanza di transcript, run_id, fingerprint del codice).


## 2. Target user e scenari

### 2.1 Retail avanzato disciplinato
Vuole un workflow giornaliero/settimanale ripetibile, controlli rischio, e trasparenza (perché buy/skip?).

### 2.2 Builder / quant retail
Vuole estendere universi/dati/modelli, ma con vincoli di audit e regressione (test, schema versionato, lint).

### 2.3 Scenari applicativi (v1.2.5)
Gli scenari operativi sono formalizzati in:
- `docs/use_cases/SCENARI_APPLICATIVI_v1.2.5.md`

**Policy di roadmap:** prima si chiude il Layer “Operational Safety” (Risk/OMS/Execution/Monitoring), poi si scala su scenari alpha aggiuntivi.


#### Definition of Done (DoD) per fase

- **Phase0 (Foundation)**: DB migrate stabile, path DB canonical, tool `db_status`/`verify_*` operativi, governance (`guardian`) green.
- **Phase1 (DataOps)**: ingest prezzi + gestione halts + DQ halt-aware con persistenza (`dq_*`), evidenza test PHASE1.
- **Phase2 (Execution)**: paper execution coerente + risk gate minimo + monitoring base (TCA/metrics) + audit trail end-to-end.


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


## UI — Operational Mapping (template)

Compila/raffina nei canonici di progetto (`docs/`) e rigenera con `guardian derive`.

| Pagina UI | A chi serve | Domanda tipica | Output |
|---|---|---|---|
| Decision Briefing | Retail | “Cosa faccio oggi?” | Lista segnali/ranking + disclosure |
| Gates & Data Quality | Retail/Dev | “I dati sono affidabili?” | Gate status + gaps |
| Audit Runs | Dev | “C’è look-ahead?” | Transcript + report |
| Forecast & Ranking | Retail | “Quali strumenti hanno miglior profilo?” | Stelle + confidence |
| NEWS-ALPHA | Retail | “Cosa muove il mercato?” | Sentiment + rating |
