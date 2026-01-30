# TODO — Work Items (GUARDIAN)

## Regole (per `guardian next`)
- Preferire formato: `WI-#### — Titolo` + `Status: OPEN`.
- Tenere i WI OPEN in cima (anche se il parser cerca il primo OPEN ovunque).
- `docs/` è **single source-of-truth**: modificare `docs/*` solo se esplicitamente in Allowlist del WI attivo.
- Ogni WI deve avere DoD verificabile. Dove possibile aggiungere: `Links`, `Code`, `Tests`, `Gate`, `Evidence`.

---

WI-0001 — Stabilizzare GUARDIAN (parser next + template init non-distruttivo)
Status: DONE

Contesto:
- Il blocco `next` deve funzionare anche con titoli senza em-dash e con whitespace “sporco”.
- L’inizializzazione `.doc/` non deve sovrascrivere file operativi già editati.

Scope:
- Rendere `scripts/guardian_next.py` robusto (header WI varianti, Status parsing, NBSP normalization, ricerca primo OPEN).
- Rendere `scripts/guardian_ops.py init` non-distruttivo su TODO/CURRENT_STATE/LOGBOOK; mantenere template in `.doc/_GUARDIAN/templates/`.
- Migrare `TODO.md` a formato WI canonico (questo file).

Allowlist:
- scripts/guardian.py
- scripts/guardian_next.py
- scripts/guardian_ops.py
- .doc/TODO.md
- .doc/_GUARDIAN/templates/*

DoD:
- `py scripts/guardian.py next` aggiorna `.doc/CURRENT_STATE.md` e registra evento in `.doc/LOGBOOK.md`.
- `py scripts/guardian.py lint` = PASS (WARN solo se motivati e stabili).
- `py scripts/guardian_ops.py init` NON sovrascrive `.doc/TODO.md` se esiste già.

---

WI-0002 — Execution schema (paper-first): tabelle DB + migrazione
Status: DONE

Links:
- FR-09 (Execution)

Contesto:
- Serve audit trail ordine/fill per colmare gap “execution layer” (PDR FR-09, GAP_REGISTER §3).

Scope:
- Definire schema minimo (nomi preliminari):
  - `execution_orders`
  - `execution_fills`
  - `positions_snapshot` (o equivalente, se necessario per auditing/monitoring)
- Integrare migrazione versionata nel sistema corrente (`src/db/migrate.py`).
- Aggiornare DataDictionary con nuove tabelle/campi (solo se parte del docset canonico previsto).

Allowlist:
- src/db/*
- src/core/*
- docs/004_DDT_DATADICTIONARY.md
- docs/005_TRACEABILITY_MATRIX.md

Code:
- src/db/migrate.py
- (TBD) file/schema: dove definisci DDL/migrazioni nel repo (deve restare sotto `src/db/*`)

Tests:
- (minimo) un test/verify che:
  - crea 1 ordine + 1 fill
  - legge i record e valida colonne chiave
  - gira su DB nuovo e su DB già migrato (idempotenza/versioning)

Gate:
- py scripts/guardian.py lint
- py scripts/guardian.py sync --clean
- py scripts/guardian.py derive
- py -m pytest

Evidence:
- Migrazione applicabile su DB vuoto e su DB esistente (idempotenza/versioning verificata).
- Tabelle `execution_*` presenti nel DB con colonne concordate.
- Traceability aggiornata: FR-09 ↔ WI-0002 ↔ code/tests.

DoD:
- Migrazione applicabile su DB vuoto e su DB esistente (idempotenza/versioning).
- Un test/verify che crea 1 ordine + 1 fill e li legge correttamente.
- Tracciabilita’: FR-09 aggiornato in traceability matrix.

---

WI-0003 — Execution runner: `scripts/execute.py` (paper broker) + lifecycle log
Status: OPEN

Links:
- FR-09 (Execution)

Contesto:
- Entry point richiesto in PDR FR-09 e Gap Register (execution layer).

Scope:
- Implementare `scripts/execute.py` che:
  - legge ranking “latest” (file/DB, formato deterministico)
  - produce ordini target (buy/sell/hold) con sizing semplice (placeholder)
  - simula fill paper applicando cost model esistente
  - scrive in `execution_orders`/`execution_fills`
- Agganciare run_id/audit trail dove opportuno.

Allowlist:
- scripts/execute.py
- src/execution/*
- src/db/*
- src/core/audit_engine.py (solo integrazioni minime)

DoD:
- `py scripts/execute.py --paper` produce almeno 1 record in `execution_orders` e `execution_fills`.
- Run ripetibile: stessa input produce stessi ordini (salvo timestamp/order_id).
- Report minimo: riepilogo ordini, fill_px, fees.

---

WI-0004 — RiskEngine v0 (pre-trade gate): limiti concentrazione + sizing + reason_code
Status: OPEN

Links:
- FR-08 (Risk)

Contesto:
- PDR FR-08 richiede separazione netta tra ranking e risk gate.

Scope:
- Creare `src/risk/risk_engine.py` con API deterministica:
  - input: ranking, portafoglio corrente (posizioni), parametri rischio
  - output: lista ordini ammessi/negati con `reason_code`
- Implementare controlli minimi:
  - max_positions, cash_reserve_pct
  - concentrazione per ticker (%)
  - risk_scalar (sizing lineare iniziale)
- Integrare in `scripts/execute.py` come gate.

Allowlist:
- src/risk/*
- src/execution/*
- scripts/execute.py
- docs/002_PDR_OBSERVER.md
- docs/005_TRACEABILITY_MATRIX.md

DoD:
- Unit tests per i controlli (ammesso/negato con reason_code deterministico).
- `execute.py` rifiuta ordini fuori limite e logga decisioni.

---

WI-0005 — Monitoring + TCA v0: slippage/fee drag + forecast vs realized metrics
Status: OPEN

Links:
- FR-10 (Monitoring/TCA)

Contesto:
- PDR FR-10 e Gap Register richiedono monitor drift e TCA (real vs simulated).

Scope:
- Calcolare TCA base da `execution_fills` vs prezzo di riferimento:
  - slippage (bp), fees, cost drag
- Calcolare metriche forecast vs realized su finestre rolling:
  - hit-rate, turnover, drawdown, cost drag (IC se applicabile)
- Salvare summary in DB e/o report markdown.

Allowlist:
- src/monitoring/*
- src/execution/*
- src/core/report_generator.py (se integrato)
- pages/08_Lifecycle_Monitor.py (solo wiring UI)

DoD:
- Report/summary generabile a comando con output deterministico.
- Almeno 1 alert su soglia configurabile (es. cost drag > X).

---

WI-0006 — UI: pagine Streamlit per execution log, risk flags, monitoring
Status: OPEN

Scope:
- Aggiungere/estendere pagine Streamlit per:
  - lista ordini/fills (filtri per run_id/data/ticker)
  - reason_code risk gate
  - metriche monitoring/TCA + alert

Allowlist:
- pages/*
- src/monitoring/*
- src/execution/*

DoD:
- Le pagine caricano senza errori con DB presente.
- I dati mostrati sono coerenti con `execution_*` tables.

---

WI-0007 — Hardening: test suite + verify commands + docs updates
Status: OPEN

Scope:
- Aggiungere test (pytest) per:
  - parsing ranking->orders
  - RiskEngine
  - schema execution + migrate
- Aggiornare canonici (PDR/DDT/Gap/Traceability) per riflettere quanto implementato (solo se in allowlist).
- Chiudere warning “derived README” (pulizia o whitelist).

Allowlist:
- tests/*
- scripts/*
- docs/*
- .doc/*

DoD:
- `py -m pytest` passa.
- Runner principali continuano a passare (`--help`/status).
- Traceability matrix aggiornata per FR-08/09/10.

---

## DONE / ARCHIVE

WI-0000 — Inizializzazione scaffolding repository
Status: DONE

