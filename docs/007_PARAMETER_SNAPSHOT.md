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
