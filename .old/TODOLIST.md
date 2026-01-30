# TODOLIST (derivato dallo stato del repo)

## Standard multi-OS per i comandi

Nei comandi in questo documento usa:
- Windows/PowerShell: `py -3.14`
- Linux/macOS: `python`

Per brevità useremo `<PY>` come placeholder dell’interprete.


**Regola di lettura**
- Le sezioni “Implementato” riflettono ciò che è già presente nel codice.
- Le sezioni “Planned / Not implemented” sono roadmap tracciate nei canonici (per evitare drift), e non devono essere interpretate come funzionalità già disponibili.

Questa lista riporta attività tecniche dedotte dalla struttura e dallo stato del repository e include anche una sezione di roadmap **Planned / Not implemented** quando necessaria per preservare i contratti (es. Retail Constraints, NEWS-ALPHA).

## A) Ordine e de-duplicazione tra `scripts/` e `src/`
- [x] Ridurre a zero i wrapper di compatibilità in `scripts/` dove esistono tool canonici in `src/tools/`.
  - Stato: rimossi `scripts/find_forced_exits.py`, `scripts/show_forced_exits.py`, `scripts/show_forced_exit_details.py`, `scripts/load_ticker_mappings_example.py`, `scripts/load_universe_membership_example.py`.
  - Golden path per tool atomici: `<PY> -m src.tools.<tool> ...`
- [x] Rimuovere entrypoint legacy/misnamed `src/tools/db_status.y.py` (non modulo canonico).
- [x] Decisione A1 (Policy A): mantenere in `scripts/` gli orchestratori/ops con logica propria (non migrare in `src/tools/`).
  - Priorità/KEEP: `ops_run_session.py`, `ops_reset.py`, `pack_session.py`, `news_alpha.py`, `setup.py`.
  - Motivazione: `src/tools/` resta riservato a CLI **atomiche** e composabili; gli orchestratori multi-step restano entrypoint operativi.
- [x] Deprecazione operativa: `scripts/patch_persist_equity.py` è **one-off ad alto rischio** — **DO NOT USE unless explicitly instructed**.

## B) Coerenza comandi `py`/`python`
- [x] Allineare README/help/commenti allo standard operativo: Windows/PowerShell `py`, Linux/macOS `python`.

## P) Repo hygiene — line endings (CRLF/LF)
- [x] Normalizzare line endings multi-OS via `.gitattributes` (LF per sorgenti/docs/config; CRLF per `*.bat`/`*.ps1`).
- [x] Aggiungere `.editorconfig` coerente (stesse regole), per ridurre churn tra IDE.
- Nota operativa: dopo l’introduzione/modifica di `.gitattributes` può essere necessario un commit una-tantum di `git add --renormalize .` (solo EOL).

## C) Hardening ingestion/backfill (stato)
Implementato nel codice:
- `data_gaps.reason_code` standardizzato
- logging range richiesto/ottenuto
- retry/backoff + timeout + dedup in-run (prezzi)
- modalità offline-by-default per `certify` con `--online` esplicito

## D) Documentazione canonica
- [x] Aggiornare i root `*.md` (README/Overview/Architecture/Data Dictionary/TODOLIST/Sezione D) per essere coerenti col codice.
 - [x] Session folder policy.


## G) CI / Automation
- [x] Aggiunta GitHub Actions CI minimale (push/PR): install deps + `compileall` + `main_test.py` (file: `.github/workflows/ci.yml`).


## D.1 Ops / Session utilities (Implemented)

- [x] `scripts/pack_session.py`: impacchetta artifacts in `reports/sessions/<session_key>/LATEST/` (no symlink; Windows-friendly).
- [x] `scripts/ops_reset.py`: `doctor` (non distruttivo) + `reset --yes` (distruttivo) per clean-room workflow su filesystem + DuckDB.
- [x] `scripts/ops_run_session.py`: wrapper one-shot `run → pack → certify → pack` con auto-run-id DB-first.

Comandi tipici (Windows/PowerShell):

- `<PY> scripts/ops_run_session.py --db .\data\sentinel_alpha.db --universe-id ALL --offline`
- `<PY> scripts/ops_reset.py doctor --db .\data\sentinel_alpha.db --scope full`



<a id="retail-constraints-checklist"></a>
## 12.6 Retail Constraints — Acceptance Checklist Addendum (Partially implemented)

Owner contrattuale: [Project Overview → Retail Contract & Constraints](PROJECT_OVERVIEW.md#retail-contract)

- **12.6.1 Dividendi & Corporate Actions (DR-1)**
  - Stato: **Partially implemented**
  - Implemented: Policy B (cash flows) supportata nella simulazione portafoglio via `include_dividends` (default OFF) + disclosure nel report.
  - Planned: ingestion/coverage corporate actions (split/merge) + FX dividends; eventuale Policy A (adjusted prices).
- **12.6.2 Min trade size + commission incidence filter**
  - Stato: **Implemented (min trade notional)**
  - Implemented: filtro `min_trade_notional` + contatori di skip in report.
  - Planned: threshold esplicito su commission incidence (round-trip costs / notional) come gate.
- **12.6.3 Human Delay Buffer**
  - DoD: stress test delay (intraday/sessione) + regola decisionale su alpha decay; disclosure.
- **12.6.4 Survivorship / delisted / coverage**
  - DoD: policy coverage e penalità conservativa; disclosure su strumenti non coperti.
- **12.6.5 Cost-to-run audit**
  - DoD: contatori costi (provider/CPU) + stima TCO e break-even.
- **12.6.6 Whole shares + cash drag**
  - Stato: **Partially implemented**
  - Implemented: `whole_shares` (default ON) + contatori di skip; `cash_reserve_pct` introduce cash drag in modo conservativo.
  - Planned: reporting dedicato della serie cash drag/idle cash.


## 12.7 NEWS-ALPHA v0.1 (Implemented)

- [x] Pipeline deterministica offline-by-default: fixtures → scoring → aggregazione → write su DuckDB.
- [x] Scrittura su `recs` con `firm="NEWS-ALPHA"` e `rating` vincolato a `BUY|HOLD|DOWNGRADE`.
- [x] Cache deterministica `sentiment_cache` con `MODEL="lexicon-v1"` e `text_hash` SHA-256.
- [x] Collector Google News RSS allineato al contratto di test:
  - `--offline-parse` su raw XML locale
  - `--online` bloccato senza `NEWS_ALPHA_ALLOW_ONLINE=1`
  - output: `--out-fixtures` + `--stats-file`
- [x] Suite test dedicata: `test_news_alpha_pipeline` + `test_news_alpha_rss_collector`.

### 12.7.1 Roadmap (post v0.1, Planned / Not implemented)

#### v0.2 — Historical backfill + Hybrid fusion (NEW, Wave 7H)


- [ ] **History lane (GDELT daily bulk, Events + GKG)**: storage immutabile raw + manifest.
  - `data/news_alpha/history/gdelt1/events/raw/YYYY/YYYYMMDD.export.CSV.zip`
  - `data/news_alpha/history/gdelt1/gkg/raw/YYYY/YYYYMMDD.gkg.csv.zip` (+ opz. `gkgcounts`)
  - `data/news_alpha/history/gdelt1/manifests/manifest_<stream>_<from>_<to>.json`
- [ ] **Profiling-first (census)** su 30–60 giorni: generare report top-k per guidare filtri e mapping.
  - Events: `EventCode`, `ActorName`, `ActorType`, `domains`, distribuzione tone.
  - GKG: `Themes`, `Organizations`, `Persons` (e, se presenti, location).
  - Output: `reports/news_alpha/profile/gdelt1/<stream>/profile_<from>_<to>_*.{csv,json}`
- [ ] Introdurre `FilterSpec` deterministica (JSON): `config/news_alpha/gdelt_filter_spec.json`.
- [ ] Mapping deterministico entity/actor→ticker (CSV canonico): `config/news_alpha/entity_ticker_map.csv`.
- [ ] Parser TSV → fixtures “news-like” deterministiche (JSONL) compatibili con `src/news_alpha/run.py`.
  - Output: `data/news_alpha/history/gdelt1/fixtures/<stream>/YYYY-MM-DD.jsonl`
- [ ] Gate minimo history (offline): missing days / parse error rate / coverage.
  - Output: `reports/news_alpha/gates/gdelt_history_gate_<ts>.{json,md}`
- [ ] Espandere universi a 100–150 ticker **solo** dopo coverage gate (evitare diluizione del segnale).
- [ ] Implementare fusione ibrida: `S_total = w*S_gnews + (1-w)*S_gdelt`, con `w` funzione di coverage/quality e mai 1.0 senza ablation.
- [ ] (Opz.) Integrare audit trail in `data_gaps(kind="news")` **solo** dopo definizione contrattuale (DR-3).

- [ ] Normalizzare placeholder `update_news()` per usare `firm="NEWS-ALPHA"` (evitare collisioni con “istituzionale”).
- [ ] Valutare schema dedicato `news_*` **solo se necessario** (via `src/db/migrate.py`, idempotente, backward-compatible).
- [ ] Implementare Credibility Matrix (10y) con shrinkage e drift alerts.
- [ ] Implementare Star Score con D5 hard gate e reporting deterministico.
- [ ] Aggiungere LLM reproducibility contract (prompt_hash + cache + model pin) se/solo se LLM adottato.


## Wave 6 — Forecasts, Stars & Ranking (closure) — DONE (v0.1)

- [x] Contratto Forecast/Stars/Ranking definito (spec: `WAVE6_FORECAST_STARS_RANKING_SPEC.md` v0.1).
- [x] Ranking engine deterministico implementato (`src/forecast/ranking.py`) + CLI (`<PY> -m src.tools.forecast_rankings`).
- [x] Leak-safe calibration: usa solo `audit_trades.signal_date < asof_date` (test: `test/test_forecast_ranking_wave6.py`).
- [x] Report `AUDIT_COMPLETE_<run_id>.md` include sezione **Pre-trade Forecasts & Ranking** con link/preview artifact.
- [x] Streamlit: pagina `pages/06_Forecasts_Ranking.py` (import-safe; nessuna chiamata di rete).
- [x] Persistenza DB: **non richiesta** in v0.1 (nessuna migration; output via artifacts in `reports/`).

**DoD / Evidence**
- `<PY> -m pytest test/test_forecast_ranking_wave6.py -q`
- `<PY> main_test.py`
- `<PY> scripts/sentinel.py certify`

**Operational**
- Pre-run (default ON): `SENTINEL_ENABLE_FORECASTS=1` (default) / disable with `SENTINEL_ENABLE_FORECASTS=0`.
- Artifacts: `reports/FORECAST_RANKING_<run_id|YYYY-MM-DD>.{json,md}` + `reports/FORECAST_RANKING_LATEST.json`.

## E) Time navigation (AS-OF) + Lifecycle monitor (Entry TTL=0) — Partially implemented

Riferimento contrattuale: [DR-4](PROJECT_OVERVIEW.md#dr-4-forecast-validity--asof) e [DR-5](PROJECT_OVERVIEW.md#dr-5-trading-room-vs-backtest).

- [x] Tool CLI `<PY> -m src.tools.alert_lifecycle` (classificazione deterministica AS-OF, TTL=0).
- [x] Streamlit: pagina **Lifecycle Monitor (AS-OF / TTL=0)** con KPI sintetici, timeline conteggi e tabella aggregata + drill-down.
- [x] Modalità esplicita **Trading Room (decisionale)** vs **Backtest (simulazione)** dove disponibile (selettore/toggle).
- [ ] Estendere la navigazione AS-OF e la legenda/tooltip standard a tutte le pagine decisionali (Forecasts & Ranking, decision briefing, ecc.).
  - [ ] ranking/forecast: caricamento artefatto per data o generazione su richiesta
  - [ ] query su `recs` e `prices` (e, solo in modalità Backtest, `audit_*`): niente futuro oltre `now_date`
- [ ] Implementare funnel lifecycle “a imbuto” (EXTRACTED → ENTERABLE → PREDICTED → TRADABLE → EXPIRED/TRADED) con percentuali.

### E.1 UX / Italianization (NEW)
- [ ] Tradurre tutto in italiano nelle pagine decisionali (titoli, label, colonne, assi, legende).
- [ ] Standardizzare tooltips (“nuvolette”) con glossary unico (TTL=0, AS-OF, Provenienza, Stati).
- [ ] Riordinare i contenuti per livello (Executive → Operativo → Tecnico) con progressive disclosure (collapsible).

## F) Strict provenance gate (No test data) — Partially implemented

- [x] UI/Trading Room: blocco operativo (un record senza `headline + source_url + published_at` non può diventare TRADABLE) e contatori dedicati.
- [ ] Definire gate canonico fail-fast: nessun segnale può essere “decisionale” se manca provenance minima verificabile.
- [ ] Integrare un tool dedicato (es. `<PY> -m src.tools.verify_provenance`) e cablarlo in `certify` (fail-fast).
- [ ] Standardizzare denylist domini placeholder (`example.*`, `localhost`, ecc.) e impedire la persistenza in DB da fixtures non-production.

## Appendice (deprecated) — Wave 7L checklist (Decision UI AS-OF)

Nota: questa checklist è mantenuta in modo canonico in **Sezione E** (Time navigation + Lifecycle monitor).


Owner contrattuale: [DR-4](PROJECT_OVERVIEW.md#dr-4-forecast-validity--asof).

Implemented subset (snapshot):
- Pagina Lifecycle Monitor: selettore AS-OF + KPI + tabella (Trading Room)


- [ ] **UI: selettore temporale AS-OF** (date picker) usato da tutte le pagine decisionali (forecast/ranking/alert funnel).
- [ ] **Lifecycle funnel (EXTRACTED → ENTERABLE → PREDICTED → TRADABLE → EXPIRED / TRADED)** derivato (no schema changes) e mostrato come infografica "a imbuto".
- [ ] **Tabella "Tradable oggi"** come primo contenuto, con tooltip standard (signal_date, intended_entry_date, provenance, forecast, reason).
- [ ] **Legenda + colori stabili** per ogni stato (coerenti su timeline/grafici/tabelle).
- [ ] **Postcast OPEN/CLOSED**: distinguere forecast "chiuso" (outcome calcolabile) vs "aperto" (outcome non ancora disponibile) senza confonderlo con TRADABLE.

### Wave 7A — Strict provenance / no test data (gate)
- [ ] Bloccare a livello tool/UI la promozione a "decisionale" per record privi di provenance (`headline`, `source_url`, `published_at`) o con domini placeholder.
- [ ] Aggiungere un gate dedicato (es. `<PY> -m src.tools.verify_provenance`) e integrarlo in `certify` (fail-fast).
- [ ] Aggiungere contatori e disclosure nel report (quanti record violano provenance; se zero, dichiarare "SAFE").

