# NEWS-ALPHA Orchestration Workplan

## Standard multi-OS per i comandi

Nei comandi in questo documento usa:
- Windows/PowerShell: `py -3.14`
- Linux/macOS: `python`

Per brevità useremo `<PY>` come placeholder dell’interprete.


This file is the single source of truth for the “zip-by-zip / wave” workflow.
It is intentionally simple and meant to survive interrupted sessions.

Note on naming:
- Project folder name (human-facing): **NEWS-ALPHA** (can be any local folder name; canonical identity is NEWS-ALPHA)
- Internal identifiers (code/CLI/docs): **NEWS-ALPHA**

## Invariants (must hold for every change)

- Work only on the current ZIP snapshot.
- Git hygiene: repository multi-OS; line endings normalizzate via `.gitattributes` + `.editorconfig` (LF per sorgenti/docs, CRLF per `*.bat`/`*.ps1`).
  - Se queste regole cambiano, prevedere un commit dedicato di `git add --renormalize .` (solo EOL).
- PR/push must be green on GitHub Actions CI (`.github/workflows/ci.yml`): install + compileall + `main_test.py`.
- Every task/prompt must declare an explicit **file allowlist**.
- Parallel work is allowed only when file scopes are disjoint **and** shared contracts are not modified.
- Each patch must include: list of files touched + verification evidence (commands + pass/fail).

### Shared contracts (must not drift)

Treat these as “hard interfaces”:
- DB schema in `src/db/migrate.py` (tables/keys/columns)
- Verify gates in `src/tools/verify_run.py` and runner wiring
- Core audit semantics in `src/core/audit_engine.py`
- Report disclosure contract in `reports/AUDIT_COMPLETE.md`

## Definition of Done (DoD)

- `<PY> main_test.py` passes.
- `<PY> scripts/sentinel.py certify` completes with a SUCCESS run and writes `reports/AUDIT_COMPLETE.md`.
- `<PY> scripts/sentinel.py verify --db data/sentinel_alpha.db` passes on the latest SUCCESS run.
- GitHub Actions CI is green for the commit/PR (install + compileall + `main_test.py`).

## Release discipline (canonical hygiene)

For each green checkpoint, update:
- `CHANGELOG.md` (what changed, why)
- the relevant `RUNLOG_W*.md` (evidence: commands + key outputs + run_id)
- `WORKPLAN.md` (wave status + deltas)
 - [x] Session folder policy.

## Waves

### Wave 0 — Baseline Audit (DONE)

- Baseline test suite: PASS
- Verify gates on latest SUCCESS run: PASS
- Reference run_id: `85d1fd68ae5a4c08986cf4227101dc62`

Artifacts:
- `RUNLOG_W0_BASELINE.md`

### Wave 1 — Contract Pack (REINFORCED) (DONE)

Goal: add contract/integration tests that lock critical interfaces (DB schema, verify semantics, report disclosure).

Key contracts:
- Verify semantics around forced exits vs `data_gaps`
- DB primary key enforcement on critical audit tables
- Report disclosure of `run_id` + `code_fingerprint`
- Report disclosure of resolved run config (sourced from `audit_runs.config_json`)
- Offline guard contract for price backfill (no network when offline)

Artifacts:
- `ZIP_01_CONTRACT_PACK_REINFORCED.zip`

### Wave 2 — Parallel Lanes (DONE)

Lanes integrated (file scopes were disjoint):
- Lane E (scripts hygiene)
- Lane C (backfill hardening)
- Lane F (report disclosure)

Artifacts:
- `LANE_E_OVERLAY.zip`, `LANE_C_OVERLAY.zip`, `LANE_F_OVERLAY.zip`

### Wave 3 — Integration (serial) (DONE)

Applied overlays in deterministic order: E → C → F.

Gate results (Windows environment):
- `<PY> main_test.py`: PASS
- `<PY> scripts/sentinel.py verify --db data/sentinel_alpha.db`: PASS

Artifacts:
- `RUNLOG_W3_INTEGRATION.md`

### Wave 4 — Contract & Canonical Alignment (DONE)

Purpose: eliminate drift between documentation and code, and harden retail failure modes without changing core semantics.

Delivered (2A–2E):
- 2A: `DATA_DICTIONARY.md` aligned to `src/db/migrate.py` (schema is source of truth).
- 2B: restored DR-3 in `PROJECT_OVERVIEW.md` (forced exits / data gaps) and aligned it to verify semantics.
- 2C: dividends disclosure aligned to “capability vs run setting” (Policy B exists; `SENTINEL_INCLUDE_DIVIDENDS` controls enablement).
- 2D: removed stale README references (refusi).
- 2E: standardized on `.env` config (deprecated PowerShell local config).

Additional Wave 4 hardening:
- Added pre-audit input gate: `<PY> -m src.tools.verify_inputs`.
  - Ensures eligible signals reference tickers covered in `prices` after `ticker_mappings` + survivorship filtering.
  - Splits metrics: `eligible_signals` (enterable) vs `eligible_signals_total` (includes right-censored).
- Fixed offline backfill behavior: OFFLINE blocks network providers but allows injected offline-safe providers (unit tests).
- Report is self-contained: resolved defaults persisted in `audit_runs.config_json` and disclosed in `AUDIT_COMPLETE.md`.

Evidence:
- `RUNLOG_W4_CONTRACT_ALIGNMENT.md`

### Wave 5 — Ticker Mapping Hardening (DONE)

Goal: harden `ticker_mappings` integrity and reduce retail symbol drift issues.

Delivered (Wave 5A):
- Standard ticker notation for class shares: **DOT** (e.g., `BRK.B`) as project convention.
- New gate: `<PY> -m src.tools.verify_ticker_mappings` (fails on overlap, invalid ranges, effective cycles).
- Runner integration: `scripts/sentinel.py` esegue `verify_ticker_mappings` prima di `verify_inputs`.
- Report disclosure: `AUDIT_COMPLETE.md` include contatori "Mapping gate (ticker_mappings)".

Delivered (Wave 5B):
- Added conservative ticker normalization (dash-to-dot for single-suffix class shares) and applied it consistently in:
  - the pre-audit inputs gate coverage computation (`verify_inputs` / `verify_signal_price_coverage`)
  - the audit engine eligibility query (`run_trade_audit`) so gate and audit are consistent
- Expanded input-gate disclosure in report and CLI summary:
  - counters for `normalized_signals` and `mapped_signals`
- `src.tools.ticker_mappings` now normalizes tickers on load to reduce drift.

Next:
- Optional: mapping suggestion helper (non-automatic) for common reticker patterns.
- Heuristic/contract su chain length (quando comprimere catene di alias).

### Wave 5C — Audit Observability & Streamlit Terminal (DONE)

Goal: rendere l'audit **operativamente osservabile** end-to-end, senza ambiguità e senza dipendere da variabili “mancanti”.

Delivered:
- Report `AUDIT_COMPLETE.md` ora include:
  - **Audit Timeline (phase-by-phase)** con durata e key metrics.
  - **Phase Details**: dump strutturato per fase (utile per spiegare “cosa è successo” e “perché”).
  - **Artifacts & Operational Logs**: paths espliciti per DB, report e transcript.
  - Salvataggio anche come archivio immutabile: `reports/AUDIT_COMPLETE_<run_id>.md` (senza rompere il path legacy `reports/AUDIT_COMPLETE.md`).
- Runner `scripts/sentinel.py`:
  - Transcript file per ogni `run` / `certify` (con run_id nel filename) e path propagato nel report.
  - L'output dei comandi è replicabile: il transcript funge da “black box recording” certificabile.
- Streamlit Terminal multi-page (directory `pages/`):
  - **Pipeline Control**: comandi reali `scripts/sentinel.py` (status/migrate/test/verify/run/certify).
  - **Gates & Data Quality**: stato di `verify_ticker_mappings` e `verify_inputs` senza lanciare l'audit.
  - **Audit Runs**: browsing `audit_runs` + apertura report archiviati + transcript.
  - **Trades & Equity**: analisi di `audit_trades`/`audit_equity` per run.
  - **Data Gaps & Backfill**: osservabilità `data_gaps` (provider/status/reason_code/rows_upserted).

Operator notes:
- Consiglio operativo: usare sempre `<PY> scripts/sentinel.py certify` come entrypoint “green checkpoint” (migrate + test + gates + audit + report).

## Wave 6 — Forecasts, Stars & Ranking (CLOSURE — DONE)

Goal: produrre un output “chiudibile” lato utente: **forecast**, **star rating**, e **ranking** dei ticker, con audit trail e cruscotto Streamlit dedicato.

Scope (must be deterministic/offline-by-default):
- **Forecast**: generazione di un punteggio/probabilità/expected-return per ticker e data (baseline deterministica; modelli più complessi solo se esplicitamente abilitati).
- **Stars**: rating 1–5 che combina (a) strength del segnale, (b) quality/coverage dati, (c) coerenza mapping, (d) (opz.) affidabilità storica della sorgente.
- **Ranking**: top-N per data con motivazione “explainable” (componenti del punteggio) e tracciamento dei filtri/constraint applicati.

Delivered (spec: WAVE6_FORECAST_STARS_RANKING_SPEC.md v0.1):
- New deterministic module `src/forecast/` that produces:
  - expected-return proxy (forecast_return_pct)
  - confidence score
  - percentile-based star rating (1–5)
  - stable ranking with deterministic tie-breakers
- New CLI tool: `<PY> -m src.tools.forecast_rankings`.
  - Writes `reports/FORECAST_RANKING_<run_id or asof_date>.{md,json}`
  - Updates `reports/FORECAST_RANKING_LATEST.json`
- Runner integration:
  - `<PY> scripts/sentinel.py forecast`
  - `run`/`certify` optionally call forecasts when `SENTINEL_ENABLE_FORECASTS=1` (default ON).
- Report integration:
  - `reports/AUDIT_COMPLETE.md` and `reports/AUDIT_COMPLETE_<run_id>.md` include a new section
    **Pre-trade Forecasts & Ranking**, with artifact paths and Top-25 preview.
- Streamlit:
  - New page `pages/06_Forecasts_Ranking.py` (reads latest JSON; filter + drill-down).
- Tests (offline + deterministic): `test/test_forecast_ranking_wave6.py`.

Gates:
- `verify_inputs` e `verify_ticker_mappings` restano prerequisiti.
- Nuovo gate “ranking_contract”: nessun ticker in ranking senza coverage prezzi e senza provenance (firm, rating, reason).

Acceptance commands:
- `<PY> main_test.py`
- `<PY> scripts/sentinel.py certify`
- `<PY> scripts/sentinel.py forecast` (optional standalone)
## Parallel lane — NEWS-ALPHA (DONE v0.1; can run in parallel with Wave 5)

### Purpose
Provide a deterministic news-derived signal source that writes into `recs` and can be consumed by the audit engine.

### Hard constraints
- Must not modify DB schema or core audit/gates/runner.
- Must be implementable by merging only allowlisted files.

### Canonical documents
- `NEWS_ALPHA_SPEC.md` (the specification)
- `NEWS_ALPHA_TASK_PROMPT.md` (copy/paste prompt for an independent implementer)

### Allowed file scope (for the independent task)
- `src/news_alpha/**`
- `scripts/news_alpha.py` (optional)
- `test/test_news_alpha_*.py`
- `test/fixtures/news_alpha/**`
- the two NEWS-ALPHA docs above
### Status

- Implementazione v0.1 completata e allineata a:
  - `NEWS_ALPHA_SPEC.md`
  - `test/test_news_alpha_pipeline.py`
  - `test/test_news_alpha_rss_collector.py`

### Verification (DoD evidence)

Comandi di verifica (snapshot-level):
- `<PY> -m pytest test/test_news_alpha_pipeline.py -q`
- `<PY> -m pytest test/test_news_alpha_rss_collector.py -q`
- `<PY> main_test.py`
- `<PY> scripts/sentinel.py certify`



## Wave 7H — NEWS-ALPHA Historical Backfill & Hybrid Fusion (NEW — PLANNED)

### Goal
Costruire **3–12 mesi di storico** per il segnale NEWS-ALPHA tramite ingestion batch offline (storico “puro”), e poi evolvere
verso una soluzione **ibrida** dove l’archive proprietario (Google News RSS) diventa progressivamente significativo e paritetico.

### Non-negotiables (must not break)
- Nessuna regressione su DoD attuale (Wave 0–6). `<PY> main_test.py` e `<PY> scripts/sentinel.py certify` devono restare verdi.
- Default posture: offline (nessuna rete) per parse/ETL e per i run di audit.
- Nessuna modifica di schema in prima iterazione; se e solo se inevitabile, migration via `src/db/migrate.py` idempotente e backward-compatible.

### Phase 7A — Canonical extension (docs)
- Aggiornare i canonici per formalizzare: lane storica (GDELT bulk), lane live (Google RSS), policy di fusione ibrida, coverage gate.
- Deliverables: update di `NEWS_ALPHA_SPEC.md`, `TECHNICAL_ARCHITECTURE.md`, `PROJECT_OVERVIEW.md`, `WORKPLAN.md`, `TODOLIST.md`, `README.md`.

### Phase 7B — Historical provider (GDELT daily bulk) ingestion (implementation)

**Principio chiave:** *profiling-first*.
Prima censiamo e misuriamo (30–60 giorni), poi fissiamo una `FilterSpec` deterministica, poi eseguiamo il backfill 3–12 mesi.

Deliverables (planned):
- Downloader idempotente + raw-store immutabile (filesystem) per **Events** e **GKG**.
- Manifest (hash/checksum + lista file + gaps) + stats JSON (range richiesto/ottenuto, contatori, error taxonomy).
- Parser TSV → fixtures “news-like” deterministiche (JSONL) **compatibili con `src/news_alpha/run.py`**.
- Profiling outputs (census): top `EventCode`, top `ActorName`, top `domains` (Events); top `Themes/Organizations/Persons` (GKG).

**Folder layout (planned, no new DB):**
- `data/news_alpha/history/gdelt1/events/raw/YYYY/YYYYMMDD.export.CSV.zip`
- `data/news_alpha/history/gdelt1/gkg/raw/YYYY/YYYYMMDD.gkg.csv.zip` *(GKG full)*
- `data/news_alpha/history/gdelt1/gkg/raw/YYYY/YYYYMMDD.gkgcounts.csv.zip` *(opzionale: counts stream)*
- `data/news_alpha/history/gdelt1/manifests/manifest_<stream>_<from>_<to>.json`
- `data/news_alpha/history/gdelt1/fixtures/<stream>/YYYY-MM-DD.jsonl`
- `reports/news_alpha/profile/gdelt1/<stream>/profile_<from>_<to>_*.{csv,json}`

**CLI (planned; coerente con `scripts/news_alpha.py`):**
- `<PY> scripts/news_alpha.py history download --stream events|gkg|both --date-from YYYY-MM-DD --date-to YYYY-MM-DD [--raw-dir ...]`
- `<PY> scripts/news_alpha.py history profile  --stream events|gkg|both --date-from ... --date-to ... [--raw-dir ...] [--out ...]`
- `<PY> scripts/news_alpha.py history fixtures --stream events|gkg|both --date-from ... --date-to ... --filter-spec config/news_alpha/gdelt_filter_spec.json --entity-map config/news_alpha/entity_ticker_map.csv`

File allowlist (planned, disjoint):
- `src/news_alpha/history/**` (nuovo)
- `scripts/news_alpha.py` (estensione subcommand `history`)
- `test/test_news_alpha_history_*.py`
- `test/fixtures/news_alpha/history/**`
- `config/news_alpha/gdelt_filter_spec.json` (nuovo)
- `config/news_alpha/entity_ticker_map.csv` (nuovo)
- `config/news_alpha/allow_missing_dates.txt` (nuovo)

### Phase 7C — Mapping + coverage gates (minimum viable)

Deliverables (planned):
- Mapping deterministico entity/actor→ticker (CSV canonico + tie-break per `priority` e finestre temporali).
- Coverage report offline (per universo/ticker): counts, buchi, dedup rate.
- Gate minimo (fail-fast):
  - **Missing days**: giorni richiesti senza raw file (con allowlist `config/news_alpha/allow_missing_dates.txt`).
  - **Parse error rate**: `rejected_rows / total_rows` (WARN > 0.5%, FAIL > 2%).
  - **Coverage**: `tickers_with_items / tickers_in_universe` per giorno e rolling 60g (WARN se mediana < 20% o se >50% ticker “muti”).

Artifact di gate (planned):
- `reports/news_alpha/gates/gdelt_history_gate_<ts>.json`
- `reports/news_alpha/gates/gdelt_history_gate_<ts>.md`

### Phase 7D — Hybrid fusion (progressive)
Deliverables (planned):
- Calcolo di `S_gdelt`, `S_gnews` e fusione `S_total = w*S_gnews + (1-w)*S_gdelt`.
- `w(ticker,day)` funzione di coverage/quality; mai 1.0 senza evidenza (ablation).
- Opzionale: logging `data_gaps(kind='news')` solo quando definito un contratto con i gate DR-3.

### Acceptance (planned)
- Test offline: history downloader (mock), parser deterministico, mapping deterministico.
- End-to-end: generazione recs NEWS-ALPHA su un range storico (fixtures) + `<PY> scripts/sentinel.py certify` verde.

### Wave 7L — AS-OF Navigation & Lifecycle Monitor (TTL=0) (PARTIALLY IMPLEMENTED)

Goal: rendere la UI decisionale comprensibile e auditabile introducendo una navigazione temporale (AS-OF) e stati lifecycle coerenti con Entry TTL=0.

Implemented subset (snapshot):
- Tool `<PY> -m src.tools.alert_lifecycle` per classificazione deterministica AS-OF (TTL=0).
- Pagina Streamlit **Lifecycle Monitor (AS-OF / TTL=0)** con KPI, timeline 14gg e tabella aggregata con drill-down.
- Separazione esplicita **Trading Room (decisionale)** vs **Backtest (simulazione)** dove disponibile (vedi DR-5).

Remaining deliverables (planned):
- Unificare la navigazione AS-OF e le legende/tooltip su *tutte* le pagine decisionali (ranking/forecast/alert funnel).
- Funnel lifecycle “a imbuto” (EXTRACTED → ENTERABLE → PREDICTED → TRADABLE → EXPIRED/TRADED) come infografica stabile.
- Gate “fail-fast” di provenance (no test data) integrato nel runner (oltre al blocco UI).

Evidence (DoD):
- `<PY> main_test.py` PASS.
- Runlog che dimostra un caso non vuoto su `now_date` in cui esiste `t+1` prezzi e spiega un caso vuoto per right-censoring.



### Wave 8 — Streamlit Decision UI (Italianization + Infographics) (NEW — PLANNED)

Purpose: trasformare il cruscotto Streamlit da “terminale tecnico” a **Trading Room decisionale**: chiaro, sintetico, con drill-down controllato.

Scope (no schema changes):
- Traduzione completa in italiano (titoli, label, colonne, legende, tooltip) per le pagine decisionali.
- Standardizzazione dei tooltip (“nuvolette”) con glossary unico (TTL=0, AS-OF, Provenienza, Stati lifecycle).
- Riordino delle informazioni per fase e livello di dettaglio (Executive → Operativo → Tecnico).
- Introduzione di infografiche leggere e deterministiche:
  - KPI cards (Totale, Tradable oggi, In attesa dati, Scaduti, Bloccati provenance)
  - Timeline conteggi (14–30 giorni) con legenda stabile
  - Funnel lifecycle (imbuto) con percentuali
  - Tabella aggregata (1 riga per ticker/giorno) + drill-down controllato

Hard constraints:
- La Trading Room non deve consultare `audit_trades` (backtest-only) e non deve mostrare “trade eseguito” senza un layer di execution esplicito.
- Nessun uso di dati di prova o placeholder: se presenti nel DB, devono restare **non operabili** e contati come violazioni.

File allowlist (planned, UI-only):
- `app.py`
- `pages/**`
- Canonici root (solo se necessari per allineamento): `README.md`, `PROJECT_OVERVIEW.md`, `TECHNICAL_ARCHITECTURE.md`, `WORKPLAN.md`, `TODOLIST.md`, `CHANGELOG.md`

Acceptance (DoD evidence):
- `<PY> main_test.py` PASS
- `<PY> -m streamlit run app.py` (pagine decisionali navigabili; nessuna eccezione runtime)


### (Opzionale) Session folders / pack

Per archiviare artifacts per sessione (no symlink):

```powershell
<PY> scripts/pack_session.py pack --action certify --db .\data\sentinel_alpha.db --universe-id ALL --offline
```
