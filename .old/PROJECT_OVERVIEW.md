# Project Overview: NEWS-ALPHA

**Scope:** questo documento è il “contratto” di alto livello del progetto e contiene i **Decision Records** (DR) che devono essere citati dagli altri canonici.

**Regola di lettura**
- **Implemented in current snapshot**: solo ciò che è verificabile nel codice del repository.
- **Planned / Not implemented**: roadmap e requisiti futuri, marcati esplicitamente come non implementati.

<a id="implemented"></a>
## Implemented in current snapshot
NEWS-ALPHA esegue una pipeline di audit/backtest che:
- mantiene una base dati locale in **DuckDB** (schema canonico in `src/db/migrate.py`)
- genera output certificabile su:
  - `audit_runs` (run e metadata)
  - `audit_trades` (trade ledger auditato)
  - `audit_equity` (equity curve e metriche per data)
  - report Markdown in `reports/AUDIT_COMPLETE.md`
- registra esiti e anomalie del backfill in `data_gaps` (range richiesto/ottenuto, reason code, contatori inserted/upserted)
- include strumenti/UI locali per osservabilità e triage (Streamlit multipage), inclusa una vista **Lifecycle (AS-OF / TTL=0)** per Trading Room


## Cosa NON è (nel codice attuale)
- Non è un sistema completo di “news intelligence” real-time: `update_news()` in `src/sentinel_alpha.py` è dichiarato esplicitamente come placeholder.
- Non include dataset licenziati (es. componenti indice): l’utente popola `universe_membership` e `ticker_mappings` tramite tool.


<a id="planned"></a>
## Planned / Not implemented

Questa sezione raccoglie requisiti e visione che **non** risultano implementati nello snapshot corrente.  
Sono mantenuti nei canonici per evitare drift e per rendere esplicito cosa è “aspettativa” vs “realtà”.

- **NEWS-ALPHA**: lane parallela deterministica **implementata in v0.1** (collector → fixtures → `recs` + `sentiment_cache`).
  - Planned v0.2: storico batch (GDELT **Events + GKG**, daily bulk) con approccio **profiling-first** (census → FilterSpec → backfill 3–12 mesi) + fusione ibrida progressiva con archive Google News (coverage-gated, deterministic fusion).
  - Owner architetturale: [Technical Architecture → NEWS-ALPHA](TECHNICAL_ARCHITECTURE.md#news-alpha)
- **Retail Contract & Constraints** (dividendi/corporate actions, commission incidence, whole shares, human delay, cost-to-run audit, delivery/alerts).  
  Owner contrattuale: [Appendice Retail Contract & Constraints](#retail-contract)

<a id="decision-records"></a>## Operational observability (Implemented)

Ogni run certificato è diagnostico e riproducibile tramite:

- `AUDIT_COMPLETE.md` con sezione **Audit Timeline (phase-by-phase)** e **Phase Details**
- artifacts per `run_id` (report archiviato + transcript runner)
- gate pre-audit (`verify_ticker_mappings`, `verify_inputs`) con disclosure nel report

Obiettivo: consentire triage rapido (dove/quanto/perché) incrociando report, transcript e suite test.


## Decision Records (DR)

I DR sono “autorità” per scelte che impattano audit e certificabilità. Gli altri documenti **devono** linkare qui, non duplicare.

<a id="dr-1-dividends"></a>
### DR-1 — Dividendi e Corporate Actions (Price Convention Policy)

**Obiettivo:** evitare di “vendere alpha” che in realtà è un effetto di dividendi/split/corporate actions o di data quality retail.

Policy (lettere **authoritative** in questo repository):
- **Policy A (Baseline, certificabile): Adjusted prices for performance**  
  Prestazioni calcolate su serie aggiustate per split/dividendi (o equivalente definito e ripetibile), con disclosure nel report.
- **Policy B (Evolutiva): Unadjusted prices + cash dividend flows**  
  Prezzi non aggiustati + flussi di cassa dividendi modellati nel ledger (tax/withholding inclusi se dichiarati).
- **Policy C (Solo disclaimer): Ignore dividends**  
  Ammissibile solo con disclaimer esplicito **“NOT CERTIFIABLE”**.

**Compliance nello snapshot corrente (verificato dal codice):**
- Prezzi: `prices.price`/`prices.open_price` sono **unadjusted**; il backfill retail (yfinance) è `auto_adjust=False` (Close/Open).  
  Quindi **Policy A** (serie adjusted) non è implementata nello snapshot corrente.
- Dividendi: la tabella `dividends` esiste nello schema e la simulazione di portafoglio può applicare i dividendi come **cashflow** (Policy B) quando `include_dividends=True` (knob di run; vedi anche `SENTINEL_INCLUDE_DIVIDENDS`).  
  Default operativo: `include_dividends=False` (dividendi ignorati).

**Disclosure minima richiesta (Implemented):**
- Il report (`reports/AUDIT_COMPLETE.md`) deve dichiarare:
  - price convention (unadjusted vs adjusted)
  - **stato del modeling dividendi** (ENABLED/DISABLED) e, se abilitato, withholding rate e contatori (eventi/gross/net)
  - limiti di copertura (tabella `dividends` vuota/parziale, provider, ecc.)

<a id="dr-2-timing"></a>
### DR-2 — Timing Policy (No Future Data Contract)

**Baseline (certify):** **T+1 execution**  
Segnale al giorno D → esecuzione alla **prima sessione successiva** (D+1 open se disponibile; fallback su close se open non disponibile).

**Implementazione nello snapshot corrente (verificata):**
- In `src/core/audit_engine.py` la data di acquisto è la **MIN(prices.date) > signal_date** e il prezzo di buy usa `COALESCE(open_price, price)`.  
  Stato: **Implemented**.

**Stress mode (opzionale, Planned):**
- “Strict conservative” come modalità di stress (es. ritardo addizionale o regole più conservative) usata solo per robustezza e con disclosure.

**Fast-mode (Planned):**
- Modalità time-sensitive (intraday/near-real-time) ammessa solo con:
  - controlli di **alpha decay**
  - ablation obbligatorie
  - disclaimer su riduzione di auditabilità/reproducibilità.


<a id="dr-3-forced-exits--data-gaps"></a>
### DR-3 — Forced Exits & Data Gaps (Auditability Contract)

**Obiettivo:** rendere auditabili (e quindi “certificabili” o “disclaimabili”) i casi in cui un trade non può chiudere con un’uscita “regolare” per cause di **copertura dati** o **fine campione**.

**Principio:** un forced exit non deve essere “silenzioso”. Deve essere:
1) classificato in `audit_trades.exit_reason`
2) (se dovuto a gap/dato mancante) supportato da audit trail in `data_gaps`
3) conteggiato nel report (A7.0 / disclosure)

**Reason codes (authoritative):**
- `FALLBACK_LAST_PRICE` — forced exit dovuto a data issue (copertura insufficiente / calendar mismatch / forward data non disponibile *dove sarebbe richiesto*).  
  Requisiti:
  - `audit_trades.exit_is_fallback = TRUE`
  - `verify_run` deve trovare almeno una riga in `data_gaps` per lo stesso `run_id` (tipicamente `kind='prices'`) che documenti range richiesto/ottenuto e outcome (SUCCESS/FAILED/SKIPPED).
- `MARK_TO_MARKET_END_OF_DATA` — fine campione (right-censoring): l’holding period non è realizzabile perché i prezzi terminano prima della data target.  
  Requisiti:
  - `audit_trades.exit_is_fallback = TRUE`
  - **non** richiede `data_gaps` (non è un fallimento di ingestion: è un limite strutturale del campione).

**Reporting minimo (Implemented):**
- Il report deve riportare:
  - conteggio forced exits totali
  - breakdown `FALLBACK_LAST_PRICE` vs `MARK_TO_MARKET_END_OF_DATA`
  - nota interpretativa: `MARK_TO_MARKET_END_OF_DATA` implica right-censoring e può alterare metriche su orizzonti brevi.




<a id="dr-4-forecast-validity--asof"></a>
### DR-4 — Forecast Validity Window (Entry TTL=0) & AS-OF Navigation Contract

**Obiettivo:** rendere auditabile e comprensibile la differenza tra: (a) forecast *calcolabile* (enterable), (b) forecast *azionabile* (tradable) e (c) forecast *scaduto* (expired), senza confondere questi concetti con la disponibilità del postcast (outcome) o con l’esecuzione di un trade.

**Policy (authoritative):**
- **Entry TTL = 0**: ogni forecast è tradabile solo nella **prima sessione utile successiva** al `signal_date` (T+1, vedi DR-2).
- `intended_entry_date` è deterministica: `MIN(prices.date) WHERE prices.date > signal_date`.
- Un forecast è **TRADABLE** se e solo se `now_date == intended_entry_date` e passa i vincoli/policy di eseguibilità.
- Un forecast è **EXPIRED** se `now_date > intended_entry_date` e non risulta eseguito.
- La disponibilità del **postcast** (forecast “chiuso”) è indipendente dalla tradabilità: un forecast può essere *expired ma non ancora chiuso* (outcome non disponibile) oppure *chiuso ma mai tradato* (backtest-only).

**No test data / provenance gate (non negoziabile):**
- Un record non deve mai essere considerato TRADABLE se manca provenance minima (es. `source_url`, `headline`, `published_at` oppure un identificatore provider equivalente). In assenza di provenance, il record può essere tracciato (diagnostica) ma deve essere **bloccato** lato decisionale.

**Compliance nello snapshot corrente:**
- **Implemented:**
  - DR-2 (T+1 execution) nel core audit engine.
  - Lifecycle monitor deterministico **AS-OF / TTL=0** (tool + UI): classificazione `TRADABLE/WAITLIST/EXPIRED` e blocco decisionale su provenance minima.
- **Planned / Not implemented:**
  - Estensione della navigazione AS-OF a *tutte* le pagine decisionali (ranking/forecast/alert funnel) e unificazione delle legende/tooltip.
  - Gate dedicato “verify_provenance” (fail-fast) integrato nel runner (oltre ai contatori e blocchi UI).



<a id="dr-5-trading-room-vs-backtest"></a>
### DR-5 — Trading Room vs Backtest (Separation Contract)

**Obiettivo:** evitare ambiguità operative tra *opportunità decisionale* (Trading Room) e *simulazione storica* (Backtest).

**Principio:**
- La **Trading Room** mostra ciò che è *operabile* **as-of** (senza dati futuri) e non deve implicare “trade eseguito” se non esiste un layer di esecuzione esplicito.
- Il **Backtest** (o simulazione) usa `audit_trades` e `audit_equity` come output storico per valutare performance e failure modes.

**Policy (authoritative):**
- In modalità **Trading Room** la UI deve calcolare e mostrare stati lifecycle e KPI usando solo:
  - `recs`, `prices`, `universe_membership`, `ticker_mappings` (+ artifacts `FORECAST_RANKING_*` se necessari)
  - e deve trattare `audit_trades` come **backtest-only** (non consultato).
- In modalità **Backtest** la UI può usare `audit_trades`, ma deve etichettare esplicitamente la vista come **Simulazione/Backtest**.
- Se una singola pagina offre entrambe le viste, deve esistere un **toggle** esplicito e una legenda coerente.

**Razionale:**
- Riduce il rischio di interpretare output storici come “azioni suggerite oggi”.
- Mantiene auditabilità: decisione (as-of) e simulazione (storico) restano separabili e confrontabili.

**Compliance nello snapshot corrente:**
- **Partially implemented:** separazione esplicita in UI/strumenti dove disponibile.
- **Planned:** introdurre un layer di “execution log” dedicato (paper/live) se e solo se si decide di aggiungere operatività reale.


## Componenti principali (riferimenti)
- Runner operativo: `scripts/sentinel.py` (certify/status/verify/migrate/test/run)
- Schema DB (canonical owner): `src/db/migrate.py`
- Motore audit: `src/core/audit_engine.py` (utilizza `universe_membership`, `ticker_mappings`, `ticker_halts`, `market_halts`)
- Backfill prezzi (hardening + audit): `src/data/price_backfill.py`
- API stabile per pipeline/UI: `src/intelligence_engine.py`
- UI: `app.py` (Streamlit)
- Runner pipeline: `main.py` (usato da `certify`)

Cross-reference: vedi [Technical Architecture](TECHNICAL_ARCHITECTURE.md) e [Data Dictionary](DATA_DICTIONARY.md).


<a id="retail-contract"></a>
## Appendice — Retail Contract & Constraints

Questa appendice formalizza assunzioni e vincoli “retail” che influenzano direttamente certificabilità e aspettative di performance.  
Ogni punto è classificato come **Implemented** o **Planned**.

### Obiettivo operativo (contratto)
Massimizzare performance **netta** e ripetibile (after-friction / after-cash-drag / after-tax *se modellata*) vs benchmark semplice, su orizzonte 1–3 anni, evitando auto-inganni da data-quality o look-ahead.


### D1) Dividendi & Corporate Actions (Data Quality Retail)
- Stato: **Partially implemented** (Policy B: cash dividends)
- Implemented: la simulazione di portafoglio può applicare cash dividends dalla tabella `dividends` come cashflow (flag `include_dividends`, default OFF) con disclosure nel report.
- Planned: ingestion/coverage corporate actions (split/merge) + FX dividends (se necessario) + policy alternativa (Adjusted prices).


### D2) Min trade size + commission incidence filter
- Stato: **Implemented** (min trade notional + contatori)
- Implemented: filtro deterministico `min_trade_notional` e contatori di skip nel report; estendibile a soglia di commission-incidence.
- Planned: threshold esplicito su commission incidence (round-trip costs / notional) come gate.

### D3) Human Delay Buffer (latenza operativa umana)
- Stato: **Planned**
- Requirement: stress test sistematico di delay (es. ritardo intraday o sessione successiva) e regola decisionale: se l’alpha collassa → dichiarare “non adatto a retail non full-time” o introdurre filtri anti-gap.

### D4) Survivorship bias / delisted / coverage
- Stato: **Partially implemented**
- Implemented: gating su `universe_membership` e mapping ticker (`ticker_mappings`) sul signal_date.
- Planned: policy esplicita per titoli delisted/non coperti (disclosure + penalità conservativa).

### D5) Cost-to-run audit (TCO operativo)
- Stato: **Planned**
- Requirement: contatori costi (provider calls, volumi, CPU) + stima costi mensili e break-even.


### D6) Whole shares + cash drag
- Stato: **Partially implemented**
- Implemented: `whole_shares` (default ON) con rounding e contatori di skip; la `cash_reserve_pct` introduce cash drag in modo conservativo.
- Planned: reporting esplicito della serie di cash drag/idle cash e stress test sistematici.

### D7) Delivery / alerts (operatività)
- Stato: **Planned**
- Requirement: delivery entro finestra utile pre-market D+1 con sintesi motivazioni e “star score”; audit trail della consegna.

### Traceability
Questi vincoli sono tracciati come checklist in [TODOLIST → 12.6 Retail Constraints](TODOLIST.md#retail-constraints-checklist).

## Forecasts, stars & ranking (Implemented — Wave 6)

Chiusura “user-facing” del progetto: generazione di forecast e ranking (top picks) con star rating 1–5.

Requisiti non negoziabili:
- determinismo a parità di DB/fixtures
- niente ranking senza coverage prezzi e provenance (`firm`, `rating`, motivazione)
- explainability: breakdown del punteggio per ticker

Implementazione:
- CLI: `<PY> -m src.tools.forecast_rankings` (o `<PY> scripts/sentinel.py forecast`)
- Artifacts:
  - `reports/FORECAST_RANKING_<run_id or asof_date>.{json,md}`
  - `reports/FORECAST_RANKING_LATEST.json`
- No future-leak: la calibrazione usa soltanto `audit_trades.signal_date < asof_date`.
