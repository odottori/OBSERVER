# Data Dictionary: NEWS-ALPHA

**Scope:** schema e semantica del database DuckDB usato dal progetto.

**Owner canonico dello schema:** `src/db/migrate.py`.

**Regola:** questo documento deve essere uno *specchio* dello schema in `src/db/migrate.py`.
Se una tabella/colonna è presente nello schema, deve essere documentata qui; se non è presente, qui non deve apparire.

Riferimenti contrattuali:
- Dividendi / price convention: [DR-1](PROJECT_OVERVIEW.md#dr-1-dividends)
- Timing / no-future-data: [DR-2](PROJECT_OVERVIEW.md#dr-2-timing)
- Forced exits / data gaps: [DR-3](PROJECT_OVERVIEW.md#dr-3-forced-exits--data-gaps)
- Forecast validity / time navigation (Entry TTL=0): [DR-4](PROJECT_OVERVIEW.md#dr-4-forecast-validity--asof)
- Trading Room vs Backtest (separation): [DR-5](PROJECT_OVERVIEW.md#dr-5-trading-room-vs-backtest)

---

## Principi di interpretazione

### 1) Price convention (unadjusted)
- `prices.price` è **close unadjusted**.
- `prices.open_price` è **open unadjusted** (se disponibile).

Lo schema non include una serie “adjusted close” (Policy A non implementata nello snapshot corrente).

### 2) Timing contract (T+1)
- Il ledger segnali (`recs`) espone una data “legacy” (`recs.date`) e opzionalmente un timestamp (`recs.published_at`).
- L’audit engine costruisce in modo deterministico `signal_date`, `buy_date`, `sell_date` e persiste i risultati in `audit_trades`.
- Entry retail: `buy_price = COALESCE(open_price, price)`.

**Nota DR-5 (Trading Room vs Backtest):**
- `audit_trades` e `audit_equity` sono output **storici** del backtest/audit. Non sono un “execution log”.
- Le viste decisionali (Trading Room) devono derivare stati e KPI da `recs`+`prices` (e artifacts), e trattare `audit_*` come backtest-only.


**Estensione contrattuale (DR-4, Entry TTL=0):**
- `intended_buy_date` coincide concettualmente con `intended_entry_date` (T+1) e deriva da `prices`.
- Un forecast e' **tradabile** solo nel giorno `intended_buy_date` (TTL=0). Dopo tale data, se non eseguito, e' **scaduto** e deve restare "backtest-only".
- La classificazione TRADABLE/EXPIRED/PENDING e la navigazione temporale **AS-OF** sono derivate (UI/tooling) e non richiedono migrazione schema.

**Nota (DR-5):** `audit_trades` e `audit_equity` sono output storici di audit/simulazione; non rappresentano un log di esecuzione reale. La Trading Room deve trattarli come *backtest-only* salvo introduzione esplicita di un layer di execution.

### 3) Dividends (Policy B come cashflow)
- La tabella `dividends` esiste nello schema e la simulazione di portafoglio può applicare i dividendi come cashflow **se e solo se** `include_dividends=True` (knob di run).
- Se `include_dividends=False`, i dividendi sono **ignorati** (equivalente operativo di Policy C) e la disclosure deve riportarlo.

### 4) Forced exits e data gaps
- Alcuni trade possono chiudere in modo “forzato” per ragioni non economiche (es. fine campione) usando reason code auditabili (`audit_trades.exit_reason`).
- Le richieste/risultati di backfill (successi/fallimenti/range ottenuto) sono tracciati in `data_gaps`.

---

## Tabelle

### `metadata`
Anagrafica strumenti (enrichment / mapping provider) e campi necessari a friction model (es. Tobin tax).

**Chiave primaria:** `ticker`

**Colonne**
- `ticker` (VARCHAR, PK)
- `sector` (VARCHAR)
- `market` (VARCHAR) — es. `US`, `EU`, `ITALY`
- `currency` (VARCHAR)
- `instrument_type` (VARCHAR) — es. `EQUITY`, `ETF`, `DERIVATIVE`
- `is_tobin_tax` (BOOLEAN, default FALSE)
- `ftt_rate` (DOUBLE) — frazione del notional (es. `0.001` = 0.10%)
- `yf_symbol` (VARCHAR) — simbolo provider (yfinance)
- `stooq_symbol` (VARCHAR) — simbolo provider (stooq)

---

### `prices`
Serie prezzi giornaliera per ticker.

**Chiave primaria:** (`date`, `ticker`)

**Colonne**
- `date` (DATE)
- `ticker` (VARCHAR)
- `price` (DOUBLE) — close unadjusted
- `open_price` (DOUBLE) — open unadjusted (nullable)
- `source` (VARCHAR) — provenienza (es. `legacy`, `stooq`, `yfinance`)
- `fetched_at` (TIMESTAMP) — timestamp del fetch/insert

**Note**
- Per l’execution retail (DR-2): `buy_price` usa `COALESCE(open_price, price)`.

---

### `dividends`
Dividendi (cashflow) per strumenti.

**Chiave primaria:** (`ticker`, `ex_date`)

**Colonne**
- `ticker` (VARCHAR)
- `ex_date` (DATE)
- `pay_date` (DATE)
- `amount` (DOUBLE)
- `currency` (VARCHAR)
- `source` (VARCHAR)
- `fetched_at` (TIMESTAMP)

**Note**
- La simulazione di portafoglio può applicare questi dividendi come cashflow **solo** quando `include_dividends=True`.
- Se la tabella è vuota o incompleta, l’impatto può essere nullo/parziale e deve essere dichiarato nel report.

---

### `data_gaps`
Audit trail operativo per ingestion/backfill (prezzi/news, ecc.).

**Chiave primaria:** non definita (tabella log).

**Colonne**
- `run_id` (VARCHAR) — run che ha generato la richiesta (se disponibile)
- `kind` (VARCHAR) — es. `prices`, `news`
- `ticker` (VARCHAR)
- `start_date` (DATE)
- `end_date` (DATE)
- `requested_at` (TIMESTAMP)
- `status` (VARCHAR) — es. `SUCCESS` | `FAILED` | `SKIPPED`
- `provider` (VARCHAR)
- `message` (VARCHAR) — dettaglio human-readable
- `rows_inserted` (INTEGER)
- `rows_upserted` (INTEGER) — insert + update (best-effort)
- `error` (VARCHAR)
- `duration_ms` (INTEGER)
- `reason_code` (VARCHAR) — classificazione standardizzata
- `requested_start_date` (DATE)
- `requested_end_date` (DATE)
- `obtained_start_date` (DATE)
- `obtained_end_date` (DATE)

**Note**
- Gate (DR-3): se esistono trade con `exit_reason='FALLBACK_LAST_PRICE'`, `verify_run` richiede evidenza in `data_gaps` per quel `run_id`.

---

### `audit_runs`
Registry dei run di audit/certificazione.

**Chiave primaria:** `run_id`

**Colonne**
- `run_id` (VARCHAR, PK)
- `started_at` (TIMESTAMPTZ)
- `finished_at` (TIMESTAMPTZ)
- `status` (VARCHAR) — `RUNNING` | `SUCCESS` | `FAILED`
- `universe_id` (VARCHAR)
- `holding_period_sessions` (INTEGER)
- `config_json` (VARCHAR) — configurazione/disclosure (incl. env)
- `code_fingerprint` (VARCHAR) — impronta codice per riproducibilità
- `notes` (VARCHAR)
- `error` (VARCHAR)

---

### `audit_trades`
Trade ledger auditato (output centrale).

**Chiave primaria:** `trade_id`

**Colonne (core)**
- `trade_id` (VARCHAR, PK)
- `run_id` (VARCHAR)
- `signal_date` (DATE)
- `buy_date` (DATE)
- `sell_date` (DATE)
- `exit_reason` (VARCHAR)
- `exit_is_fallback` (BOOLEAN)

**Colonne (strumento / contesto)**
- `ticker` (VARCHAR)
- `ticker_original` (VARCHAR)
- `firm` (VARCHAR)
- `rating` (VARCHAR)
- `market` (VARCHAR)
- `sector` (VARCHAR)
- `instrument_type` (VARCHAR)
- `mom_status` (VARCHAR)
- `risk_vol` (DOUBLE)
- `sentiment_score` (DOUBLE)

**Colonne (execution / halts)**
- `exec_shift_sessions` (INTEGER)
- `exit_shift_sessions` (INTEGER)
- `halt_reason` (VARCHAR)

**Colonne (frictions)**
- `is_tobin_tax` (BOOLEAN)
- `ftt_pct` (DOUBLE) — percentuale (0..100) applicata al notional

**Colonne (economics)**
- `buy_price` (DOUBLE)
- `sell_price` (DOUBLE)
- `gross_return_pct` (DOUBLE)
- `cost_pct` (DOUBLE)
- `net_return_pct` (DOUBLE)
- `trade_score` (DOUBLE) — score deterministico usato per dedup/selection
- `universe_id` (VARCHAR)

**Enumerazioni (exit_reason)**
- `HOLDING_PERIOD` — exit regolare (holding period raggiunto)
- `HALT_SHIFT` — exit con shift per halt
- `FALLBACK_LAST_PRICE` — forced exit per data issue (richiede audit trail in `data_gaps`, DR-3)
- `MARK_TO_MARKET_END_OF_DATA` — fine campione (right-censoring, DR-3)

---

### `audit_equity`
Equity curve (mark-to-market) e contatori operativi per data.

**Chiave primaria:** (`run_id`, `date`)

**Colonne**
- `run_id` (VARCHAR)
- `date` (DATE)
- `equity` (DOUBLE)
- `cash` (DOUBLE)
- `invested` (DOUBLE)
- `positions` (INTEGER)
- `tax_paid` (DOUBLE)
- `executed_trades` (INTEGER)
- `closed_trades` (INTEGER)

---

### `recs`
Ledger segnali (input).

**Chiave primaria:** (`date`, `ticker`, `firm`)

**Colonne**
- `date` (DATE) — publication date (legacy)
- `ticker` (VARCHAR)
- `firm` (VARCHAR)
- `rating` (VARCHAR)
- `sentiment_score` (DOUBLE)
- `headline` (VARCHAR)
- `source_url` (VARCHAR)
- `universe_id` (VARCHAR)
- `published_at` (TIMESTAMP) — opzionale (future evoluzioni intraday)

**Note (NEWS-ALPHA v0.1)**
- NEWS-ALPHA scrive su `recs` con `firm="NEWS-ALPHA"` (valore fisso).
- `rating` è vincolato a: `BUY|HOLD|DOWNGRADE` (contratto `NEWS_ALPHA_SPEC.md`).
- `headline`, `source_url`, `published_at` possono essere “rappresentativi” del gruppo aggregato (ticker-day).
- `universe_id` è valorizzato dal runner quando disponibile (compatibilità con ranking/filtri per universo).


---

### `momentum_rankings`
Feature set di momentum (contesto).

**Chiave primaria:** (`date`, `ticker`)

**Colonne**
- `date` (DATE)
- `ticker` (VARCHAR)
- `m_ret` (DOUBLE)
- `rnk` (INTEGER)
- `signal` (VARCHAR)

---

### `universes`
Catalogo universi.

**Chiave primaria:** `universe_id`

**Colonne**
- `universe_id` (VARCHAR, PK)
- `name` (VARCHAR)
- `market` (VARCHAR)
- `description` (VARCHAR)

---

### `universe_membership`
Membership storica per universo (survivorship-bias control).

**Chiave primaria:** (`universe_id`, `ticker`, `start_date`)

**Colonne**
- `universe_id` (VARCHAR)
- `ticker` (VARCHAR)
- `start_date` (DATE)
- `end_date` (DATE) — nullable
- `source` (VARCHAR)
- `notes` (VARCHAR)

---

### `ticker_mappings`
Mapping ticker time-bounded (symbol changes / corporate actions).

**Chiave primaria:** (`alias_ticker`, `start_date`)

**Colonne**
- `alias_ticker` (VARCHAR)
- `canonical_ticker` (VARCHAR)
- `start_date` (DATE)
- `end_date` (DATE) — nullable
- `source` (VARCHAR)
- `notes` (VARCHAR)

---

### `ticker_halts`
Halt per ticker (execution feasibility).

**Chiave primaria:** (`ticker`, `start_date`)

**Colonne**
- `ticker` (VARCHAR)
- `start_date` (DATE)
- `end_date` (DATE)
- `reason` (VARCHAR)
- `source` (VARCHAR)

---

### `market_halts`
Halt di mercato (execution feasibility).

**Chiave primaria:** (`market`, `start_date`)

**Colonne**
- `market` (VARCHAR)
- `start_date` (DATE)
- `end_date` (DATE)
- `reason` (VARCHAR)
- `source` (VARCHAR)

---

### `sentiment_cache`
Cache sentiment deterministica (repeatability).

**Chiave primaria:** `text_hash`

**Colonne**
- `text_hash` (VARCHAR, PK)
- `text` (VARCHAR)
- `score` (DOUBLE)
- `model` (VARCHAR)
- `computed_at` (TIMESTAMP)

**Note (NEWS-ALPHA v0.1)**
- `text` è il testo **normalizzato** usato per calcolare `text_hash` (repeatability).
- `model` è pinned a `lexicon-v1` per v0.1 (no drift tra run).


---

### `audit_signal_decisions`
Decision ledger (tracciabilità intra-run: eseguito/skip/dedup).

**Chiave primaria:** `decision_id`

**Colonne**
- `decision_id` (VARCHAR, PK)
- `run_id` (VARCHAR)
- `signal_date` (DATE)
- `ticker_original` (VARCHAR)
- `ticker` (VARCHAR)
- `firm` (VARCHAR)
- `rating` (VARCHAR)
- `universe_id` (VARCHAR)
- `intended_buy_date` (DATE)
- `buy_date` (DATE)
- `exec_shift_sessions` (INTEGER)
- `intended_sell_date` (DATE)
- `sell_date` (DATE)
- `exit_shift_sessions` (INTEGER)
- `decision` (VARCHAR) — `EXECUTED` | `SKIPPED` | `DROPPED_DEDUP`
- `skip_reason` (VARCHAR)
- `halt_reason` (VARCHAR)
- `created_at` (TIMESTAMPTZ)
---

## NEWS-ALPHA history lane (v0.2, Planned) — no schema changes

Questa estensione **non** introduce nuove tabelle in prima iterazione.
Lo storico news viene conservato su filesystem (`data/news_alpha/history/gdelt1/...`) e trasformato in fixtures JSONL.
La persistenza nel DB resta invariata: `recs` (firm=`NEWS-ALPHA`) e `sentiment_cache` (model versionata).

Se in futuro sarà inevitabile uno schema `news_*`, dovrà passare da `src/db/migrate.py` in modo idempotente e backward-compatible.
