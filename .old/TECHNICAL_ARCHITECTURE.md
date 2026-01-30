# Technical Architecture: NEWS-ALPHA

**Regola di lettura**
- Descrive ciò che è verificabile nel codice e, dove utile, esplicita roadmap **Planned / Not implemented** in modo separato.
- Le policy “contrattuali” (prezzi/dividendi, timing, forced exits, offline-first) sono in [Project Overview → Decision Records](PROJECT_OVERVIEW.md#decision-records).

Questa architettura è descritta **in base al codice presente nel repository**.

---

## Standard comandi multi-OS (`<PY>`)

Nei runbook, `<PY>` indica il comando da usare per invocare Python:

- Windows/PowerShell: `py -3.14` (o `py`)
- Linux/macOS: `python`

---

## 1) Layout repository (component inventory)

- `scripts/` — entrypoint operativi
  - `sentinel.py`: runner CLI (golden path: `certify`)
  - `pack_session.py`: impacchetta artifacts in cartelle sessione deterministiche (no symlink)
  - `ops_reset.py`: utility ops per `doctor`/`reset` (pulizia artifacts + pulizia DB DuckDB-aware)
  - `ops_run_session.py`: wrapper one-shot `run → pack → certify → pack` (DB-first auto-run-id)
  - `news_alpha.py`: runner operativo NEWS-ALPHA (lane separata; offline-by-default)
  - `setup.py`: bootstrap/repair (stdlib-only by design)
  - `patch_persist_equity.py`: **DEPRECATE** (one-off ad alto rischio) — **DO NOT USE unless explicitly instructed**
  - tool canonici (golden path): `src.tools.forced_exits`, `src.tools.universe_membership`, `src.tools.ticker_mappings` (invocabili via `<PY> -m ...`)
- `src/` — implementazione core
  - `db/migrate.py`: owner canonico dello schema DuckDB
  - `db/audit_store.py`: persistenza run + ledger audit
  - `core/audit_engine.py`: logica deterministica di audit (trades/equity)
  - `data/price_backfill.py`: backfill prezzi multi-provider + `data_gaps`
  - `tools/*`: tool canonici invocabili via `<PY> -m ...` (verify/status/forced exits)
  - `intelligence_engine.py`: wrapper orchestratore (compatibilità con `main.py`/`app.py`)
  - `sentinel_alpha.py`: ingestion news/prezzi (placeholder / opzionale)
- `reports/` — report generati (es. `AUDIT_COMPLETE.md`)
- `data/` — DB DuckDB e artefatti dati locali
- `test/` — test suite

---

## 2) Flusso “certify” (golden path)

### Observability artifacts (Implemented)

- Runner transcript per `run_id` (stdout/stderr e comandi) in `reports/*_TRANSCRIPT_<run_id>.txt`
- Report archiviato per run: `reports/AUDIT_COMPLETE_<run_id>.md`
- `AUDIT_COMPLETE.md` include **Audit Timeline (phase-by-phase)** + **Phase Details**
- (Opzionale) Session folders: `scripts/pack_session.py` copia artifacts in `reports/sessions/<session_key>/LATEST/` per ridurre drift e duplicazioni di file “latest”.

Questo rende ogni run “auditabile” end-to-end anche offline.


- `<PY> scripts/sentinel.py certify --db data/sentinel_alpha.db`

Sequenza (osservabile in `scripts/sentinel.py`):
1. migrazione schema: `<PY> -m src.db.migrate --db <DB>`
2. test suite (default): `<PY> main_test.py`
Questi controlli base sono replicati anche in CI (compileall + main_test).
3. preflight gates: `<PY> -m src.tools.verify_ticker_mappings` → `<PY> -m src.tools.verify_inputs`
3b. strict provenance gate: `<PY> -m src.tools.verify_provenance`
4. (Wave 6, default ON) pre-trade forecasts/ranking: `<PY> -m src.tools.forecast_rankings`
5. pipeline: `<PY> main.py` (produce report + persiste audit)

**Offline-first:** in modalità `certify` il runner imposta `SENTINEL_OFFLINE=1` e `SENTINEL_ALLOW_ONLINE_BACKFILL=0` salvo `--online`.  
Questo garantisce che la certificazione non dipenda da rete o provider esterni.

Output attesi:
- `reports/AUDIT_COMPLETE.md`
- insert/update in `audit_runs`, `audit_trades`, `audit_equity` (vedi [Data Dictionary](DATA_DICTIONARY.md))

---

## 3) Pipeline applicativa (`main.py` + orchestratore)

- `main.py`:
  - assicura schema aggiornato
  - (opzionale) ingestion via `SentinelAlpha` (placeholder)
  - esegue audit deterministico e persiste risultati
- `src/intelligence_engine.py`:
  - genera `run_id`, calcola `code_fingerprint`
  - registra `config_json` (incl. env “disclosure-only”)
  - chiama `run_deep_audit()` (audit engine) e money management

**Nota:** `main.py` setta alcuni default con `os.environ.setdefault(...)` (non sovrascrive valori già impostati dal runner).

---

## 4) Audit engine (trade ledger → equity)

Owner: `src/core/audit_engine.py`.

Input principali:
- `recs` (segnali)
- `prices` (close/open)
- `universe_membership` + `ticker_mappings` (survivorship e mapping ticker)
- opzionali: `ticker_halts`, `market_halts` (gestione halt/shift)
- opzionali: `momentum_rankings` (contesto/feature)

Output:
- `audit_trades`: un record per trade auditato (buy/sell date, returns, reason codes)
- `audit_equity`: equity curve e metriche per data
- `audit_signal_decisions`: decision log per segnali (tracciabilità)
- `audit_runs`: metadata run, inclusi `code_fingerprint` e `config_json`

**Semantica forced exits:** vedi [DR-3](PROJECT_OVERVIEW.md#dr-3-forced-exits--data-gaps).

---

## 5) Backfill prezzi e audit trail `data_gaps`

Owner: `src/data/price_backfill.py`.

Caratteristiche:
- provider order configurabile (`SENTINEL_PRICE_PROVIDER_ORDER`)
- modalità offline: nessuna rete (`SENTINEL_OFFLINE=1`)
- retry/backoff controllabili
- dedup richieste backfill (`SENTINEL_DEDUP_BACKFILL_REQUESTS=1`)

Audit trail:
- le richieste e i fallimenti persistono in `data_gaps` (kind tipico: `prices`)
- `verify_run` richiede coerenza: se esistono trade con `exit_reason='FALLBACK_LAST_PRICE'` allora devono esistere righe in `data_gaps` per quel run

---

## 6) Tool canonici (CLI modulare)

Invocabili via `<PY> -m ...` e usati dal runner:

- `src.tools.verify_ticker_mappings` — gate pre-audit (integrità `ticker_mappings`)
- `src.tools.verify_inputs` — gate pre-audit (coverage prezzi per ticker eleggibili; applica normalizzazione conservativa dash→dot e rende disponibili i contatori `normalized_signals` / `mapped_signals`)
- `src.tools.forecast_rankings` — Wave 6: genera forecasts/stars/ranking e scrive artifacts in `reports/FORECAST_RANKING_*.{json,md}`
- `src.tools.verify_run` — gate di qualità post-run
- `src.tools.db_status` — overview del DB
- `src.tools.forecast_rankings` — Wave 6 closure: pre-trade forecasts, stars and ranking (writes artifacts in `reports/`)
- `src.tools.forced_exits` — report forced exits per run
- `src.tools.trade_audit_report` — reportistica trade-level (se presente nello snapshot)
- `src.tools.import_*` — utility import (se presenti nello snapshot)

---

## Wave 6 — Forecasts, Stars & Ranking (v0.1 spec summary)

Questa sezione cattura i vincoli “non negoziabili” della Wave 6 e deve restare coerente con `src/forecast/ranking.py` e `src/tools/forecast_rankings.py`.

### Non-negotiables
- Output deterministico (no randomness; sort/tie-break stabili).
- Offline-by-default (nessuna rete).
- Leak-safe calibration: usare solo `audit_trades.signal_date < asof_date`.
- No schema migrations: output come artifacts in `reports/`.

### Costanti (as in code)
- `N_MIN = 20`
- `N_CONF = 60`
- `W_GLOBAL = 0.25`
- `K_SENT = 0.20`
- Default exclude: `exit_reason == "FALLBACK_LAST_PRICE"`

### Ranking stability (tie-break)
Ordinamento finale stabile:
1) `stars` desc
2) `forecast_return_pct` desc
3) `confidence` desc
4) `rating` desc
5) `firm` asc
6) `ticker_effective` asc

### Artifacts
- `reports/FORECAST_RANKING_<run_id|asof_date>.json` (stable JSON, `sort_keys=True`)
- `reports/FORECAST_RANKING_<run_id|asof_date>.md`
- `reports/FORECAST_RANKING_LATEST.json`

### Verification (DoD evidence)
- `<PY> -m pytest test/test_forecast_ranking_wave6.py -q`
- `<PY> main_test.py`
- `<PY> scripts/sentinel.py certify`

---

## 7) UI locale (Streamlit)

- `app.py` (Streamlit): dashboard locale multipage.
  - **Viewer (audit/backtest):** pagine che esplorano `audit_runs`, `audit_trades`, `audit_equity` e `data_gaps`.
  - **Trading Room (decisionale):** pagine che mostrano opportunità *AS-OF* e stati lifecycle (Entry TTL=0), senza usare output storici come se fossero “azioni suggerite oggi”.

**Contratto:** vedi [DR-5](PROJECT_OVERVIEW.md#dr-5-trading-room-vs-backtest). La Trading Room non deve consultare `audit_trades`.


---

## 8) AS-OF navigation & lifecycle states (Entry TTL=0) — Partially implemented

**Implemented subset (snapshot):**
- Tool `src.tools.alert_lifecycle` (derivazione stati rispetto a `now_date`).
- Pagina Streamlit “Lifecycle Monitor (AS-OF / TTL=0)” con KPI sintetici, timeline conteggi (14gg) e tabella aggregata con drill-down.
- Modalità **Trading Room** vs **Backtest** esplicita (toggle), coerente con DR-5.

**Problema operativo:** senza una "navigazione temporale" esplicita (AS-OF) la UI tende a mostrare dati "vuoti" o non interpretabili quando l'ultima data dei segnali (`recs.date`) e la copertura prezzi (`prices`) non sono allineate. Questo crea ambiguità tra assenza dati, right-censoring e bug.

**Contratto:** la UI deve poter simulare una `now_date` (data osservata) e calcolare ogni KPI rispetto a quella data, non rispetto alla data corrente del sistema. Vedi [DR-4](PROJECT_OVERVIEW.md#dr-4-forecast-validity--asof).

### 8.1 Stati lifecycle (derivati, senza migrazione schema)
Per ogni riga `recs` (alert/segnale), definire uno "stato" derivato rispetto a `now_date`:

- **EXTRACTED**: presente in `recs` (segnale grezzo).
- **ENTERABLE**: esiste `intended_entry_date = MIN(prices.date) WHERE date > signal_date`.
- **PREDICTED**: esiste un forecast per quel segnale (artefatto Wave 6) oppure è incluso nel ranking per l'as-of selezionato.
- **POSTCAST_CLOSED**: l'outcome del forecast è calcolabile alla `now_date` (esiste copertura prezzi sufficiente fino all'orizzonte target). Lo stato è indipendente da TRADED.
- **TRADABLE (TTL=0)**: `now_date == intended_entry_date` (prima sessione utile successiva al segnale).
- **EXPIRED**: `now_date > intended_entry_date` e il segnale non risulta eseguito.
- **TRADED**: esiste trade auditato (es. `audit_trades` o `audit_signal_decisions.decision == EXECUTED`) associabile al segnale.
- **WAITLIST**: `intended_entry_date` non calcolabile (manca copertura prezzi forward) oppure mapping/universe non risolvibile.
- **ERRORLIST**: violazione contrattuale (es. ticker non mappabile, range invalidi, record non deterministico).

Nota: questi stati non richiedono nuove tabelle. Possono essere calcolati in query (DuckDB) unendo `recs`, `prices`, `audit_signal_decisions`, `audit_trades`.

### 8.2 UX: legenda, colori, tooltips
La UI deve rendere questi stati visibili con:
- colori coerenti e stabili (legend esplicita),
- tooltip che mostrano: `signal_date`, `intended_entry_date`, stato, e motivazione (why).

## 9) Strict provenance / no test data — Partially implemented

**Non negoziabile:** il progetto non deve contenere o utilizzare "dati di prova" come input operativo.

Requisiti minimi di provenance per qualunque riga "decisionale" (tradable/ranked):
- `firm` valorizzato e stabile,
- `headline` non vuoto,
- `source_url` non vuota e con dominio reale (no placeholder tipo `example.com`, `localhost`, ecc.),
- `published_at` presente (o equivalente provider).

Fino a quando un gate dedicato non è implementato, la UI deve almeno:
- **Implemented (Trading Room):** contatori e blocco operativo nella pagina Lifecycle Monitor (record senza provenance minima non diventano TRADABLE).
- contare e mostrare quante righe violano la provenance,
- bloccare la promozione a TRADABLE/ranking "user-facing".


<a id="news-alpha"></a>
<a id="news-alpha-planned"></a>
## NEWS-ALPHA (Implemented v0.1 + roadmap)

NEWS-ALPHA è una **lane parallela** (non invasiva) che genera segnali ticker-level da news e li persiste nel DuckDB
esistente, senza modificare schema, runner o audit engine.

### Scope implementato (v0.1)

**Input**
- Fixtures JSONL prodotte dal collector (Google News RSS) oppure fixture equivalenti.

**Output persistenti**
- `recs` — segnali giornalieri aggregati, consumabili dal core audit engine.
  - `firm` fisso: `NEWS-ALPHA`
  - `rating`: `BUY|HOLD|DOWNGRADE`
  - `sentiment_score` in `[-1.0, +1.0]`
- `sentiment_cache` — cache deterministica `text_hash → score` con `model="lexicon-v1"`

#### Contract details (v0.1)

**Offline/Online guard**
- Default: offline (no network).
- Online ammesso solo se `NEWS_ALPHA_ALLOW_ONLINE=1` **e** flag `--online`.

**Rating mapping (deterministico)**
- score >= +0.20 → `BUY`
- -0.20 < score < +0.20 → `HOLD`
- score <= -0.20 → `DOWNGRADE`

**Ticker normalization (required)**
- Trim + uppercase.
- Class-share standard: DOT notation (es. `BRK.B`).
- Convert dash→dot solo per pattern `^[A-Z]{1,5}-[A-Z]$` (es. `BRK-B` → `BRK.B`).

**Aggregation & dedup (deterministico)**
- Dedup intra-run per URL (se disponibile), altrimenti hash `(published_at|source|headline)`.
- Aggregazione a una riga per `(signal_date, ticker)`.
- `sentiment_score`: media (clipped a [-1, +1]).
- Provenance rappresentativa (`headline`/`source_url`/`published_at`): scegliere l’articolo con max |sentiment|; tie-break deterministico per URL lessicografico.

**Componenti**
- `src/news_alpha/collect_google_news_rss.py`
  - `--offline-parse` su raw XML locale (default posture)
  - `--online` solo se `NEWS_ALPHA_ALLOW_ONLINE=1`
  - output: `--out-fixtures` (JSONL) + `--stats-file` (JSON)
- `src/news_alpha/run.py`
  - filtri `universe_id` + range date
  - de-duplicazione deterministica e aggregazione ticker-day
  - scrittura su `recs` + `sentiment_cache`
  - diagnostica con `--rejects-file`, logging testabile
- `src/news_alpha/sentiment.py`
  - lessico deterministico (no rete), `MODEL="lexicon-v1"`
  - normalizzazione testo + hash SHA-256 (repeatability)

### Flusso dati (alto livello)

1. **Collect** (opzionale): RSS → raw XML → fixtures JSONL.
2. **Run**: fixtures → normalizzazione ticker + filtri → scoring sentiment → aggregazione → write.
3. **Consume**: `recs` è disponibile per ranking/forecast o per auditing (come qualsiasi altro firm).

### Vincoli contrattuali

- Offline-by-default: nessuna rete salvo esplicito `NEWS_ALPHA_ALLOW_ONLINE=1`.
- No future leak: eventuali calibrations/consumi devono rispettare `signal_date < asof_date`.
- Nessuna modifica di schema (`src/db/migrate.py`) o dei gate core.

### Roadmap (post v0.1, non implementata)

**v0.2 — Historical backfill + Hybrid fusion (NEW, Planned)**
- Lane H (Historical): ingestion offline di bulk files (GDELT Events; opzionale GKG/Mentions) con raw-store immutabile e manifest sha256.
- Normalizzazione verso record news-like + mapping deterministico entity/actor→ticker tramite mapping canonico (config/news_alpha/entity_ticker_map.csv).
- Coverage gate (min news rolling) e diagnostica (stats + rejects) per evitare ticker rumorosi/scarso coverage.
- Hybrid fusion progressiva: `S_total = w*S_gnews + (1-w)*S_gdelt` con `w` funzione di coverage/quality e mai 1.0 senza ablation.
- Expansion universi: target 100–150 ticker per universo, vincolata a coverage misurata.
- (Opzionale) integrazione audit trail in `data_gaps` con `kind='news'` solo quando concordato con i gate DR-3.

- Credibility Matrix (10y) + drift alerts.
- Star Score con gate D5 e report dedicato.
- Multi-agent pipeline (SCANNER/ANALYST/HISTORY/CONTRARIAN) **solo** con reproducibility contract (prompt_hash + cache + model pin), se/solo se adottata una componente LLM.

#### v0.2 — History lane (GDELT daily bulk): folder structure, naming, CLI, gates (Planned)

**Goal:** costruire 3–12 mesi di storico “puro” (offline) e alimentare la v0.1 **senza cambiare schema DB**.

##### Folder structure (canonical, no new DB)

Root consigliata (filesystem): `data/news_alpha/history/gdelt1/`

- Events
  - Raw: `events/raw/YYYY/YYYYMMDD.export.CSV.zip`
  - Manifests: `manifests/manifest_events_<from>_<to>.json`
  - Fixtures (news-like): `fixtures/events/YYYY-MM-DD.jsonl`
- GKG
  - Raw: `gkg/raw/YYYY/YYYYMMDD.gkg.csv.zip` *(GKG full)*
  - (opz.) Raw counts: `gkg/raw/YYYY/YYYYMMDD.gkgcounts.csv.zip`
  - Manifests: `manifests/manifest_gkg_<from>_<to>.json`
  - Fixtures (news-like): `fixtures/gkg/YYYY-MM-DD.jsonl`

Profiling e gating restano in `reports/`:
- Profiling: `reports/news_alpha/profile/gdelt1/<stream>/...`
- Gates: `reports/news_alpha/gates/...`

##### Naming conventions
- **Raw**: mantenere naming originario GDELT (auditabile).
- **Fixtures**: un file per giorno e per stream.
- **Derived (merge)**: se serve un merge Events+GKG, produrre `fixtures/merged/YYYY-MM-DD.jsonl` e far puntare `scripts/news_alpha.py run --fixtures` su quello.

##### CLI interface (to extend `scripts/news_alpha.py`, Planned)

Nuovo command group: `history`.

- Download raw
  - `<PY> scripts/news_alpha.py history download --stream events|gkg|both --date-from YYYY-MM-DD --date-to YYYY-MM-DD [--raw-dir ...] [--max-retries N]`
- Profiling / census (produce whitelist candidates)
  - `<PY> scripts/news_alpha.py history profile --stream events|gkg|both --date-from ... --date-to ... [--raw-dir ...] [--out reports/news_alpha/profile]`
- Build fixtures (apply FilterSpec + entity map)
  - `<PY> scripts/news_alpha.py history fixtures --stream events|gkg|both --date-from ... --date-to ... --filter-spec config/news_alpha/gdelt_filter_spec.json --entity-map config/news_alpha/entity_ticker_map.csv --out data/news_alpha/history/gdelt1/fixtures`

Nota: `run` resta invariato e consuma fixtures prodotte dal history lane.

##### Minimal gates (Planned)

- **Missing days**: differenza tra giorni richiesti e raw disponibili (con allowlist).
- **Parse error rate**: rejected/total (WARN > 0.5%, FAIL > 2%).
- **Coverage**: ticker coverage per giorno e rolling 60g (WARN se mediana < 20% o se molti ticker restano muti).

I gates producono artifacts in `reports/news_alpha/gates/` e devono essere invocabili offline.

Riferimenti:
- [NEWS-ALPHA SPEC](.appoggio/NEWS_ALPHA_SPEC.md)
- [NEWS-ALPHA NEXT CHAT PROMPT](.appoggio/NEWS_ALPHA_NEXT_CHAT_PROMPT.md)
- [TODOLIST → NEWS-ALPHA](TODOLIST.md#127-news-alpha-v01-implemented)
