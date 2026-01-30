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
