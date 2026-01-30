---
doc_id: 008_EVIDENCE_PACK
docset_version: 1.2.5
status: canonical
last_updated: 2026-01-26
---
# Evidence Pack — v1.2.5

Build date: 2026-01-26

Questo documento elenca comandi “verificabili” per dimostrare che lo snapshot è eseguibile e coerente.

> Nota: su Windows/PowerShell usare `py` invece di `python`.

## 1. Sanity checks

- Test suite: `py -m pytest`
- Stato GUARDIAN: `py scripts/guardian.py status`
- Lint docset: `py scripts/guardian.py lint`

## 2. Data layer (DuckDB)

- Migrazione schema: `py -m src.db.migrate --db data/sentinel_alpha.db`

## 3. Pipeline sentinel (audit/backtest)

- Help runner: `py scripts/sentinel.py --help`
- Status: `py scripts/sentinel.py status`
- Certify (offline default): `py scripts/sentinel.py certify`

Artefatti attesi:
- record in `audit_runs`, `audit_trades`, `audit_equity`
- transcript/summary in `reports/`

## 4. NEWS-ALPHA

- Help runner: `py scripts/news_alpha.py --help`
- Status: `py scripts/news_alpha.py status`
- Run (offline, se configurato con fixtures): `py scripts/news_alpha.py run`

Artefatti attesi:
- `sentiment_cache` popolata
- report/JSONL in `reports/news_alpha/` (se abilitato)

## 5. Forecast ranking (Wave 6)

- Help: `py -m src.forecast.ranking --help` (se esposto) oppure via sentinel
- Generate ranking: `py scripts/sentinel.py forecast --universe ALL --top-n 25`

Artefatti attesi:
- output ranking deterministico + stars
- record/report associati a `run_id`

## 6. Execution (paper-first)

- Help: `py scripts/execute.py --help`
- Paper execution: `py scripts/execute.py --top-n 10 --starting-cash 100000`

Artefatti attesi:
- tabelle `execution_orders` e `execution_fills` aggiornate
- report execution (se presente) e tracciabilità via `run_id`

## 7. Packaging sessione

- `py scripts/pack_session.py --help`
- `py scripts/ops_run_session.py --help`

## 8. Docset governance

- Sync canonici: `py scripts/guardian.py sync --clean`
- Derive brief: `py scripts/guardian.py derive`
