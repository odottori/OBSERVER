---
doc_id: SCENARI_APPLICATIVI_v1.2.5
docset_version: 1.2.5
status: support
last_updated: 2026-01-26
---
# Scenari applicativi v1.2.5 (scenario-driven)

Questo documento raccoglie scenari d’uso concreti e li traduce in:
- copertura **as-built** (stato reale del codice)
- gap per la conformità **v1.2.5**
- deliverable e criteri di accettazione per raggiungere operatività *paper* e *live*

## Nota metodologica: “copertura” su due assi

Le percentuali “di copertura” sono fuorvianti se trattate come un singolo numero.
Qui distinguiamo:

1) **Research coverage**: quanto OBSERVER supporta backtest/audit/ranking e sperimentazione.
2) **Live-readiness**: quanto OBSERVER è pronto a gestire capitale reale (risk, OMS, execution, monitoring, guardrail).

Finché Risk/OMS/Execution/Monitoring non sono chiusi, la *live-readiness* resta bassa anche se la parte research è molto avanzata.

## Assunzioni operative

- Strumento: equity/ETF liquid (close-to-close; intraday non richiesto per MVP).
- Frequenza: giornaliera (EOD), con regola conservativa T+1 dove applicabile.
- Primo target: **paper trading disciplinato**, poi live con broker adapter (paper-first).
- Vincoli retail: costi/tasse IT, limiti API, robustezza a data gaps.

## Sintesi scenari: stato e realismo (as-built vs. richiesto)

### Scenario 1 — News Sentiment Mean-Reversion
**Research coverage**: alta (NEWS-ALPHA + audit + ranking).  
**Live-readiness**: medio-bassa finché stop/OMS/monitoring non sono completi.

**Già presente (as-built):**
- NEWS-ALPHA scoring deterministico (`src/news_alpha`, `scripts/news_alpha.py`)
- Audit trail e regola temporale conservativa (DB + `audit_*`)
- Cost model + tax model IT (`src/core/cost_model.py`, `src/core/tax_model.py`)
- Paper execution baseline (`src/execution/paper_broker.py`, `scripts/execute.py`)
- Risk gate baseline (sizing statico, cash reserve) (`src/risk/risk_engine.py`)

**Mancante per paper “robusto” e live:**
- Stop-loss/exit rules (ATR-based o equivalente), trailing e cooldown
- OMS vero: lifecycle ordine/fill, stato posizioni, reconciliation
- Behavioral guardrails: discipline mode, kill-switch, hard blocks
- Monitoring: slippage, drift, anomaly alerting

**Valutazione realistica:** Scenario 1 è il “primo candidato” perché richiede estensioni coerenti con il core già esistente.

### Scenario 2 — Multi-Factor Fusion
**Research coverage**: medio-alta (shrinkage + stars + multi-source recs/sentiment).  
**Live-readiness**: dipende dal completamento del Layer 1 (Risk/OMS/Execution/Monitoring).

**Mancante (realisticamente più impegnativo di quanto sembri):**
- Factor library estesa (value/quality + definizioni robuste + data sourcing)
- Dynamic weighting/regime-aware (richiede dataset e validazione OOS)
- Performance attribution (minimo: per-fattore; avanzato: Brinson/IC attribution)
- Sizing risk-aware cross-factor (correlazioni, concentrazione)

**Valutazione realistica:** fattibile in fasi; il collo di bottiglia non è il calcolo, ma dati, definizioni e governance.

### Scenario 3 — Corporate Actions Arbitrage
**Research coverage**: bassa-media (schema e tax handling di base).  
**Live-readiness**: bassa (data collection + event engine non presenti).

**Mancante critico:**
- Collector automatizzato corporate actions (source affidabile + normalizzazione)
- Event/timing engine (pre/post split, ex-date, payment date) con regole conservative
- Risk limits specifici per event-driven e gestione di gap/delay provider

**Valutazione realistica:** lo sforzo è guidato da dati esterni; tempi molto sensibili alla qualità delle fonti.

### Scenario 4 — Tactical Sector Rotation
**Research coverage**: bassa (universe settoriale sì, macro layer no).  
**Live-readiness**: bassa.

**Mancante:**
- Macro data layer (rates/inflation/PMI) + governance
- Regime detection con validazione OOS
- Sector ETF integration + allocation engine (vincoli, turnover, costi)

**Valutazione realistica:** scenario potente ma data-heavy; si raccomanda dopo aver stabilizzato execution/risk.

### Scenario 5 — Pairs Trading Statistical
**Research coverage**: media (price history, overlay sentiment).  
**Live-readiness**: bassa, perché richiede market-neutral execution e controlli specifici.

**Mancante:**
- Selezione pairs e monitoraggio spread (z-score, half-life)
- Execution market-neutral + gestione borrow (se short)
- Detection correlation breakdown + circuit breaker

**Valutazione realistica:** non è un “addon”: è una strategia con requisiti operativi propri, da posizionare in fase avanzata.

## Impatto sul piano implementativo v1.2.5

### Layer comune (bloccante per tutti gli scenari live)
1) Risk Engine evoluto (pre/post trade)  
2) OMS + execution log + posizione/PNL accounting  
3) Paper trading realistico (slippage/spread, partial fill simulation)  
4) Monitoring + alerting + drift + audit lifecycle end-to-end

### Scenario-first recommendation
1) Chiudere **Scenario 1 in paper robusto** (MVP operabile).
2) Abilitare **Scenario 2** (multi-factor) come estensione controllata.
3) Valutare Scenario 3/4/5 in base a disponibilità dati e priorità commerciale.
