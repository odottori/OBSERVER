# AUDIT_LIFECYCLE_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Formalizzare gli stati lifecycle e il decision ledger, in modo che:

- la UI possa rappresentare correttamente stati e transizioni
- i motivi di esclusione siano espliciti (auditability)
- le “eccezioni” (fallback, halt, right-censor) siano disclosure-first

## Stati (concettuali)

### Stati pre-trade (eligibility)
- **CANDIDATE**: segnale presente in `recs` per la data as-of.
- **ELIGIBLE**: passa normalize + ticker_mappings + universe_membership.
- **ENTERABLE**: esiste `intended_buy_date` (prezzo disponibile dopo il segnale).
- **WAITLIST**: temporaneamente non enterable per halt o gap dati (policy-dependent).
- **DROPPED**: scartato (right-censored, missing prices, fuori universo, dedup).

### Stati trade (execution)
- **EXECUTED**: trade creato in `audit_trades`.
- **CLOSED**: trade chiuso con `sell_date` e `exit_reason`.
- **FALLBACK_EXIT**: uscita con prezzo fallback (disclosure).

## Decision ledger

Tabella: `audit_signal_decisions`

Minimi campi richiesti:
- ticker_original, ticker, firm, rating, universe_id, signal_date
- intended_buy_date vs buy_date (+ exec_shift_sessions)
- intended_sell_date vs sell_date (+ exit_shift_sessions)
- decision (EXECUTED/SKIPPED/DROPPED_DEDUP)
- skip_reason e/o halt_reason

## Regole di disclosure

- Ogni skip deve avere motivazione classificabile (skip_reason/reason_code).
- Ogni fallback deve essere marcato come tale e idealmente escluso dalla calibrazione forecast (default exclude_exit_reason).

