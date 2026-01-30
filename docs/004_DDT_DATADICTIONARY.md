---
doc_id: 004_DDT_DATADICTIONARY
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-30
---
# DATADICTIONARY (DuckDB) — v1.2.5

Build date: 2026-01-30

## Panoramica

OBSERVER / SENTINEL-ALPHA utilizza **DuckDB** come single source of truth locale.  
Il modello dati e’ progettato per:

- riproducibilita’ e auditability (run_id, code_fingerprint, transcript)
- backtest “certification-grade” (no survivorship bias, ticker mappings time-bounded, halts)
- realismo retail (costi transazione, tasse IT, dividendi come estensione)

### Convenzioni generali

- `DATE` e’ usato per la logica di sessione (daily).  
- `TIMESTAMPTZ`/`TIMESTAMP` sono usati per logging e provenance. Quando possibile, usare UTC.
- Le chiavi sono implementate come `PRIMARY KEY` o `UNIQUE` (in alcuni casi DuckDB materializza la chiave come UNIQUE).

### Relazioni logiche (alto livello)

- `audit_runs` 1..N `audit_trades` / `audit_equity` / `audit_signal_decisions` / `data_gaps`
- `dq_runs` 1..N `dq_findings` / `dq_metrics_daily`
- `metadata` 1..N `prices` / `dividends`
- `recs` alimenta `audit_signal_decisions` e, indirettamente, `audit_trades`

---

## DB artifacts e path canonical

- DB DuckDB: `data/sentinel_alpha.db` (default)
- Variabile ambiente (override): `SENTINEL_ALPHA_DB_PATH`
- Snapshot/backup opzionale: `data/sentinel_alpha.zip` (non usato a runtime)

**Principio operativo:** tooling e UI devono usare il path canonical (default o env var) e non hardcodare percorsi assoluti.

## DB surface by phase (vista “delivery”)

| Phase | Tag | Tabelle (principali) |
|---|---|---|
| Phase0 | `PHASE0_FOUNDATION` | `metadata`, `universes`, `universe_membership`, `ticker_mappings` |
| Phase1 | `PHASE1_DATAOPS` | `prices`, `dividends`, `market_halts`, `ticker_halts`, `data_gaps`, `dq_runs`, `dq_findings`, `dq_metrics_daily` |
| Phase2 | `PHASE2_EXECUTION` | `execution_orders`, `execution_fills`, `audit_runs`, `audit_signal_decisions`, `audit_trades`, `audit_equity` |
| Signal plane (supporto) | `PHASE2_SIGNAL` | `recs`, `sentiment_cache`, `momentum_rankings` |

> Nota: le tabelle “audit_*” sono trasversali ma vengono considerate *delivery surface* in Phase2 perché chiudono il loop end-to-end (segnale→decisione→trade→equity).

## DB required matrix (tools/pages — snapshot)

| Entrypoint | Phase | DB | Read/Write | Tabelle principali |
|---|---|---:|---|---|
| `py -m src.tools.db_status` | Phase0 | REQUIRED | R | *introspezione schema* |
| `py -m src.tools.verify_run` / `verify_provenance` | Phase0/2 | REQUIRED | R | `audit_runs`, `audit_*`, `data_gaps` |
| `py -m src.tools.dataops_prices_ingest` | Phase1 | REQUIRED | W | `prices`, `metadata` |
| `py -m src.tools.dataops_sync_halts` / `dataops_import_closures` | Phase1 | REQUIRED | W | `market_halts`, `ticker_halts` |
| `py -m src.tools.dataops_dq_prices` | Phase1 | REQUIRED | W | `dq_runs`, `dq_findings`, `dq_metrics_daily`, `data_gaps` |
| `py scripts/execute.py --paper` | Phase2 | REQUIRED | W | `execution_orders`, `execution_fills`, `audit_*` |
| `pages/11_DataOps_Control_Room.py` | Phase1 | REQUIRED | R/W | `market_halts`, `ticker_halts`, `dq_*` |
| `pages/09_Execution_Log.py` / `pages/10_Monitoring_TCA.py` | Phase2 | REQUIRED | R | `execution_*`, `audit_*` |

---

## `metadata`

Anagrafica strumenti: ticker canonico e attributi di mercato/settore, inclusi flag fiscali (Tobin/FTT) e simboli provider.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico interno (chiave primaria). |
| sector | VARCHAR | YES | Settore economico (granularita’ libera). |
| market | VARCHAR | YES | Etichetta mercato/regione (es. US, EU, ITALY). |
| currency | VARCHAR | YES | Valuta di quotazione (ISO-4217, es. USD, EUR). |
| is_tobin_tax | BOOLEAN | YES | Flag: applica Tobin/FTT (Italia) come costo transazione addizionale. |
| yf_symbol | VARCHAR | YES | Simbolo provider yfinance (se diverso dal ticker canonico). |
| stooq_symbol | VARCHAR | YES | Simbolo provider stooq (se diverso dal ticker canonico). |
| instrument_type | VARCHAR | YES | Classe strumento (EQUITY, ETF, DERIVATIVE, ...). |
| ftt_rate | DOUBLE | YES | Aliquota FTT come frazione del notional (es. 0.001 = 0.10%). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker)

## `prices`

Prezzi giornalieri (barre daily): close (obbligatorio) + open opzionale, con provenance e timestamp di inserimento.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| date | DATE | YES | Data sessione (daily). |
| ticker | VARCHAR | YES | Ticker canonico. |
| price | FLOAT | YES | Prezzo di chiusura (close). |
| open_price | FLOAT | YES | Prezzo di apertura (open), se disponibile. |
| source | VARCHAR | YES | Provenienza riga (legacy/yfinance/stooq/...). |
| fetched_at | TIMESTAMP | YES | Timestamp inserimento/aggiornamento riga. |


### Vincoli (DuckDB)

- UNIQUE: UNIQUE(date, ticker)

## `dividends`

Eventi dividendo per realismo retail (ex-date e pay-date). Nello snapshot lo schema e’ presente; l’applicazione cashflow e’ incrementale.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico. |
| ex_date | DATE | NO | Data ex-dividend. |
| pay_date | DATE | YES | Data pagamento. |
| amount | DOUBLE | YES | Importo dividendo per share/unit. |
| currency | VARCHAR | YES | Valuta importo. |
| source | VARCHAR | YES | Provenienza dato. |
| fetched_at | TIMESTAMP | YES | Timestamp inserimento. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker, ex_date)

## `recs`

Store segnali/raccomandazioni (news/analyst): per data di pubblicazione, ticker, firm e rating, con sentiment score e metadati.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| date | DATE | YES | Data pubblicazione segnale (legacy compatible). |
| ticker | VARCHAR | YES | Ticker del segnale (puo’ essere non canonico: normalizzato/mappato a runtime). |
| firm | VARCHAR | YES | Fonte/firm (es. banca d’affari, provider news). |
| rating | VARCHAR | YES | Rating discreto (BUY/HOLD/DOWNGRADE o analogo). |
| sentiment_score | DOUBLE | YES | Sentiment in [-1,+1] (deterministico, cacheabile). |
| headline | VARCHAR | YES | Titolo/news headline associata al segnale. |
| source_url | VARCHAR | YES | URL sorgente (se disponibile). |
| universe_id | VARCHAR | YES | Universe associato al segnale (ALL/US/EU o custom). |
| published_at | TIMESTAMP | YES | Timestamp pubblicazione (se disponibile). |


### Vincoli (DuckDB)

- UNIQUE: UNIQUE(date, ticker, firm)

## `momentum_rankings`

Ranking momentum giornaliero per ticker (feature/gate) con rendimento periodo e segnali discreti.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| date | DATE | NO | Data calcolo ranking. |
| ticker | VARCHAR | NO | Ticker canonico. |
| monthly_return | FLOAT | YES |  |
| rank_pos | INTEGER | YES |  |
| signal | VARCHAR | YES | Segnale discreto (es. LONG/SHORT/HOLD). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(date, ticker)

## `universes`

Catalogo universi (es. ALL/US/EU) per filtrare segnali e controllare survivorship bias.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| universe_id | VARCHAR | NO | ID universe (chiave primaria). |
| name | VARCHAR | YES | Nome descrittivo. |
| market | VARCHAR | YES | Mercato/regione prevalente (US/EU/MULTI...). |
| description | VARCHAR | YES | Descrizione testuale. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(universe_id)

## `universe_membership`

Membership storica (ticker in universo) con intervalli temporali: essenziale per backtest senza survivorship bias.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| universe_id | VARCHAR | NO | ID universe. |
| ticker | VARCHAR | NO | Ticker canonico. |
| start_date | DATE | NO | Inizio validita’ membership (inclusivo). |
| end_date | DATE | YES | Fine validita’ (inclusivo, NULL=open-ended). |
| source | VARCHAR | YES | Fonte dataset membership. |
| notes | VARCHAR | YES | Note/annotazioni. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(universe_id, ticker, start_date)

## `ticker_mappings`

Mappature alias->canonico time-bounded (corporate actions, cambio simbolo) per evitare mismatch ticker.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| alias_ticker | VARCHAR | NO | Simbolo alias (come appare nel dato grezzo). |
| canonical_ticker | VARCHAR | YES | Simbolo canonico interno. |
| start_date | DATE | NO | Inizio validita’ mapping. |
| end_date | DATE | YES | Fine validita’ mapping (NULL=open-ended). |
| source | VARCHAR | YES | Fonte mapping (manual, provider, corporate actions...). |
| notes | VARCHAR | YES | Note. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(alias_ticker, start_date)

## `ticker_halts`

Halt su singolo ticker: finestra temporale di non-tradabilita’ e reason/provenance.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico. |
| start_date | DATE | NO | Inizio halt. |
| end_date | DATE | YES | Fine halt (NULL=open-ended). |
| reason | VARCHAR | YES | Motivo halt (sospensione, delisting, market maker, ecc.). |
| source | VARCHAR | YES | Fonte informazione. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker, start_date)

## `market_halts`

Halt di mercato/paese (es. circuit breaker, chiusure straordinarie) per execution feasibility.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| market | VARCHAR | NO | Mercato/regione (es. US, EU). |
| start_date | DATE | NO | Inizio halt. |
| end_date | DATE | YES | Fine halt. |
| reason | VARCHAR | YES | Motivo halt (circuit breaker, chiusure, ecc.). |
| source | VARCHAR | YES | Fonte informazione. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(market, start_date)

## `sentiment_cache`

Cache locale deterministica del sentiment (testo normalizzato + hash) per ripetibilita’ e audit.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| text_hash | VARCHAR | NO | Hash del testo normalizzato (chiave primaria). |
| text | VARCHAR | YES | Testo normalizzato (troncato a 2000 char). |
| score | DOUBLE | YES | Sentiment score in [-1,+1]. |
| model | VARCHAR | YES | Modello usato (vader/lexicon). |
| computed_at | TIMESTAMP | YES | Timestamp calcolo (UTC). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(text_hash)

## `data_gaps`

Log operativo di gap/backfill (prezzi/news): include intervalli richiesti, esito, righe inserite e reason_code standardizzato.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| kind | VARCHAR | YES | Tipo gap (prices/news/...). |
| ticker | VARCHAR | YES | Ticker target (se applicabile). |
| start_date | DATE | YES | Inizio finestra da ottenere (normalizzata). |
| end_date | DATE | YES | Fine finestra da ottenere. |
| requested_at | TIMESTAMP | YES | Timestamp richiesta. |
| status | VARCHAR | YES | SUCCESS/FAILED/SKIPPED. |
| provider | VARCHAR | YES | Provider (yfinance/stooq/gdelt/...). |
| message | VARCHAR | YES | Messaggio sintetico esito. |
| rows_inserted | INTEGER | YES | Numero righe inserite. |
| error | VARCHAR | YES | Errore raw (se presente). |
| duration_ms | INTEGER | YES | Durata operazione. |
| run_id | VARCHAR | YES | Run che ha richiesto il backfill (se presente). |
| rows_upserted | INTEGER | YES | Numero righe inserite + aggiornate. |
| reason_code | VARCHAR | YES | Reason code standardizzato (per KPI data quality). |
| requested_start_date | DATE | YES | Inizio richiesto originario (prima di clamp/parse). |
| requested_end_date | DATE | YES | Fine richiesta originaria. |
| obtained_start_date | DATE | YES | Min date effettivamente ottenuta. |
| obtained_end_date | DATE | YES | Max date effettivamente ottenuta. |


### Vincoli (DuckDB)

- (nessun vincolo dichiarato)

## `dq_runs`

Registro esecuzioni Data Quality (PHASE1 DataOps): una riga per run DQ con finestra e stato.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | Identificativo run DQ (chiave primaria). |
| kind | VARCHAR | YES | Tipo DQ (es. DQ_PRICES). |
| started_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp inizio (UTC consigliato). |
| finished_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp fine. |
| asof_date | DATE | YES | Data as-of del controllo (daily). |
| window_days | INTEGER | YES | Finestra lookback in giorni calendario. |
| status | VARCHAR | YES | SUCCESS/FAILED/SKIPPED. |
| notes | VARCHAR | YES | Note sintetiche (parametri + conteggi). |
| error | VARCHAR | YES | Errore raw se FAILED. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id)

## `dq_findings`

Dettaglio findings DQ (PHASE1): missing/stale/invalid, compressi per intervallo.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| finding_id | VARCHAR | NO | ID finding (chiave primaria). |
| run_id | VARCHAR | YES | Run DQ associato. |
| kind | VARCHAR | YES | Tipo finding (PRICE_MISSING/PRICE_STALE/...). |
| severity | VARCHAR | YES | Severità (INFO/WARN/ERROR). |
| market | VARCHAR | YES | Mercato derivato (US/EU/...). |
| ticker | VARCHAR | YES | Ticker canonico. |
| start_date | DATE | YES | Inizio intervallo finding. |
| end_date | DATE | YES | Fine intervallo finding. |
| count | INTEGER | YES | Numero giorni nel finding (best-effort). |
| message | VARCHAR | YES | Messaggio sintetico. |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp creazione record. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(finding_id)

## `dq_metrics_daily`

Metriche aggregate per run DQ (PHASE1) per mercato + metrica.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | Run DQ. |
| asof_date | DATE | NO | Data as-of. |
| market | VARCHAR | NO | Mercato (ALL/US/EU/...). |
| metric | VARCHAR | NO | Nome metrica (tickers, findings, invalid_rows, duration_ms, ...). |
| value | DOUBLE | YES | Valore numerico. |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp inserimento. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id, asof_date, market, metric)

## `audit_runs`

Registro run di audit/certificazione: configurazione, universi, fingerprint del codice e stato esecuzione.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | Identificativo run (chiave primaria, deterministico/UUID-like). |
| started_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp inizio run (UTC consigliato). |
| finished_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp fine run. |
| status | VARCHAR | YES | Stato: RUNNING/SUCCESS/FAILED. |
| universe_id | VARCHAR | YES | Universe testato. |
| holding_period_sessions | INTEGER | YES | Holding period in sessioni (T+N, default definito nella pipeline). |
| config_json | VARCHAR | YES | Configurazione run serializzata (string JSON). |
| code_fingerprint | VARCHAR | YES | Fingerprint del codice (hash) per audit. |
| notes | VARCHAR | YES | Note manuali / annotazioni. |
| error | VARCHAR | YES | Messaggio errore (se FAILED). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id)

## `audit_signal_decisions`

Decision ledger opzionale: traccia segnali eseguiti o scartati (dedup, halt, skip) e date ‘intese’ vs effettive.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| decision_id | VARCHAR | NO | ID decisione (chiave primaria). |
| run_id | VARCHAR | YES | ID run. |
| signal_date | DATE | YES | Data segnale. |
| ticker_original | VARCHAR | YES | Ticker originale. |
| ticker | VARCHAR | YES | Ticker canonico effettivo. |
| firm | VARCHAR | YES | Fonte segnale. |
| rating | VARCHAR | YES | Rating. |
| universe_id | VARCHAR | YES | Universe. |
| intended_buy_date | DATE | YES | Buy date intesa (prima di shift). |
| buy_date | DATE | YES | Buy date effettiva. |
| exec_shift_sessions | INTEGER | YES | Shift buy. |
| intended_sell_date | DATE | YES | Sell date intesa. |
| sell_date | DATE | YES | Sell date effettiva. |
| exit_shift_sessions | INTEGER | YES | Shift sell. |
| decision | VARCHAR | YES | EXECUTED / SKIPPED / DROPPED_DEDUP. |
| skip_reason | VARCHAR | YES | Motivo skip (missing price, halt, policy). |
| halt_reason | VARCHAR | YES | Motivo halt (ticker/market). |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp creazione record. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(decision_id)

## `execution_orders`

Ledger ordini di esecuzione (paper/real): entita’ “ordine” con stato e parametri di submit.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| order_id | VARCHAR | NO | ID ordine (chiave primaria). |
| run_id | VARCHAR | YES | FK logica verso audit_runs.run_id (se presente). |
| created_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp creazione ordine (UTC consigliato). |
| ticker | VARCHAR | YES | Ticker canonico target. |
| side | VARCHAR | YES | Lato ordine: BUY/SELL. |
| quantity | DOUBLE | YES | Quantita’ (shares/unit). |
| order_type | VARCHAR | YES | Tipo ordine (MARKET/LIMIT/...). |
| limit_price | DOUBLE | YES | Prezzo limite se LIMIT, altrimenti NULL. |
| status | VARCHAR | YES | Stato ordine (NEW/FILLED/CANCELLED/...). |
| notes | VARCHAR | YES | Note/testo libero. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(order_id)

## `execution_fills`

Ledger fills/eseguiti: ogni fill rappresenta un’esecuzione (anche parziale) di un ordine.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| fill_id | VARCHAR | NO | ID fill (chiave primaria). |
| order_id | VARCHAR | YES | FK logica verso execution_orders.order_id. |
| run_id | VARCHAR | YES | FK logica verso audit_runs.run_id (se presente). |
| filled_at | TIMESTAMP WITH TIME ZONE | YES | Timestamp fill (UTC consigliato). |
| ticker | VARCHAR | YES | Ticker canonico. |
| side | VARCHAR | YES | Lato eseguito: BUY/SELL. |
| quantity | DOUBLE | YES | Quantita’ eseguita. |
| fill_price | DOUBLE | YES | Prezzo di esecuzione. |
| fees | DOUBLE | YES | Commissioni applicate (valuta di conto). |
| notes | VARCHAR | YES | Note/testo libero. |

### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(fill_id)

## `audit_trades`

Trade ledger per run: ogni trade deriva da un segnale, include shift esecutivi, motivi di uscita e performance lorda/netta.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| trade_id | VARCHAR | NO | ID trade (chiave primaria). |
| run_id | VARCHAR | YES | FK logica verso audit_runs.run_id. |
| signal_date | DATE | YES | Data segnale originale (giorno di pubblicazione). |
| buy_date | DATE | YES | Data entrata effettiva (con shift e vincoli). |
| sell_date | DATE | YES | Data uscita effettiva. |
| exit_reason | VARCHAR | YES | Motivo uscita (TARGET/HOLDING_PERIOD/HALT/FALLBACK_LAST_PRICE...). |
| exit_is_fallback | BOOLEAN | YES | Flag: uscita fallback (prezzo last known). |
| ticker | VARCHAR | YES | Ticker effettivo canonico usato per prezzi e membership. |
| firm | VARCHAR | YES | Fonte segnale. |
| rating | VARCHAR | YES | Rating del segnale. |
| market | VARCHAR | YES | Mercato (derivato da metadata o regole). |
| sector | VARCHAR | YES | Settore (derivato da metadata). |
| mom_status | VARCHAR | YES | Esito gate momentum (se applicato). |
| risk_vol | DOUBLE | YES | Volatilita’/proxy rischio usato nella gestione posizione (se presente). |
| is_tobin_tax | BOOLEAN | YES | Flag FTT applicata. |
| sentiment_score | DOUBLE | YES | Sentiment associato al segnale. |
| buy_price | DOUBLE | YES | Prezzo entrata (close o regola scelta). |
| sell_price | DOUBLE | YES | Prezzo uscita. |
| gross_return_pct | DOUBLE | YES | Rendimento lordo (%) pre-costi e pre-tasse. |
| cost_pct | DOUBLE | YES | Costo transazione totale (%) usato nel modello. |
| net_return_pct | DOUBLE | YES | Rendimento netto (%) dopo costi (tasse tracciate altrove). |
| trade_score | DOUBLE | YES | Score del trade (se applicato dal sistema). |
| universe_id | VARCHAR | YES | Universe in cui il trade e’ stato eseguito/valutato. |
| ticker_original | VARCHAR | YES | Ticker originale del segnale (prima di normalize/mapping). |
| instrument_type | VARCHAR | YES | Classe strumento. |
| ftt_pct | DOUBLE | YES | FTT effettiva usata come percentuale del notional. |
| exec_shift_sessions | INTEGER | YES | Shift entrata (sessioni) per vincoli T+1 / prezzi mancanti / halt. |
| exit_shift_sessions | INTEGER | YES | Shift uscita (sessioni). |
| halt_reason | VARCHAR | YES | Motivo di halt (ticker/market) se ha impattato l’esecuzione. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(trade_id)

## `audit_equity`

Equity curve giornaliera per run: equity, cash, investito, numero posizioni e tasse pagate.

### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| run_id | VARCHAR | NO | ID run. |
| date | DATE | NO | Data (daily). |
| equity | DOUBLE | YES | Equity totale (cash + posizioni mark-to-market). |
| cash | DOUBLE | YES | Cassa disponibile. |
| invested | DOUBLE | YES | Notional investito (approssimazione). |
| positions | INTEGER | YES | Numero posizioni aperte. |
| tax_paid | DOUBLE | YES | Tasse pagate cumulative o per giorno (dipende dalla pipeline). |
| executed_trades | INTEGER | YES | Numero trade eseguiti nel giorno. |
| closed_trades | INTEGER | YES | Numero trade chiusi nel giorno. |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(run_id, date)



