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

