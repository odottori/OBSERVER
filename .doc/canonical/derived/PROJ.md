# PROJ — Operational Project Brief

> GENERATED FILE — DO NOT EDIT  
> Source of truth: `./docs/`  
> Generated: 2026-01-26T19:26:14Z  
> Fingerprint: 5954e6cfdf1c1076

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


## UI — Operational Mapping (template)

Compila/raffina nei canonici di progetto (`docs/`) e rigenera con `guardian derive`.

| Pagina UI | A chi serve | Domanda tipica | Output |
|---|---|---|---|
| Decision Briefing | Retail | “Cosa faccio oggi?” | Lista segnali/ranking + disclosure |
| Gates & Data Quality | Retail/Dev | “I dati sono affidabili?” | Gate status + gaps |
| Audit Runs | Dev | “C’è look-ahead?” | Transcript + report |
| Forecast & Ranking | Retail | “Quali strumenti hanno miglior profilo?” | Stelle + confidence |
| NEWS-ALPHA | Retail | “Cosa muove il mercato?” | Sentiment + rating |
