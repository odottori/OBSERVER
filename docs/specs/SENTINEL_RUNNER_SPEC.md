# SENTINEL_RUNNER_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Definire il contratto operativo del runner `scripts/sentinel.py`:

- CLI minimale e stabile
- run_id, transcript e posture offline/online
- integrazione con schema owner e tool di verifica

## Comandi supportati

- `migrate`: crea/aggiorna schema DuckDB e seed universi base
- `test`: esegue suite test
- `run`: esegue audit run (operativo)
- `certify`: esegue audit run in postura “certification-grade” (offline-by-default)
- `verify`: verifica un run_id (consistenza e policy)
- `forecast`: genera ranking a stelle (Wave 6)
- `status`: summary DB e ambiente

## Run ID

- Variabile ambiente: `SENTINEL_RUN_ID`
- Se assente e il comando e’ in {"run","certify","verify"}, il runner genera un run_id e lo preserva.

## Transcript

- `run` -> `reports/RUN_TRANSCRIPT_<run_id>.txt`
- `certify` -> `reports/CERTIFY_TRANSCRIPT_<run_id>.txt`
- Transcripts sono best-effort: non bloccano l’esecuzione.

## Offline/Online posture

- Flag:
  - `--offline` forza offline
  - `--online` abilita online backfill
- Precedenza:
  1) `--online`
  2) `--offline` / `--no-backfill`
  3) `certify` default offline

Variabili ambiente rilevanti:
- `SENTINEL_ALLOW_ONLINE_BACKFILL`
- `SENTINEL_OFFLINE`
- `SENTINEL_PRICE_PROVIDER_ORDER`
- `SENTINEL_DISABLE_YFINANCE` (default 1)

## Disclosure defaults (retail)

Il runner imposta:
- `SENTINEL_DIVIDEND_POLICY = B`
- `SENTINEL_TIMING_MODE = T_PLUS_1`

Nota: nello snapshot questi switch sono *disclosure* (registrati nei report) e non necessariamente alterano tutta la logica economica.

