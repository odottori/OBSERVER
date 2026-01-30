# NEWS_ALPHA_SPEC.md

Spec version: v0.1  
Build date: 2026-01-24

## Scopo

Definire la lane NEWS-ALPHA:

- raccolta (RSS/History) con posture online guardata
- scoring sentiment deterministico
- dedup e aggregazione
- persistenza in DuckDB (recs + sentiment_cache)

Runner: `scripts/news_alpha.py`

## Postura online (guardrail)

Azioni online richiedono **ENTRAMBI**:
- `--online`
- `NEWS_ALPHA_ALLOW_ONLINE=1` oppure `--allow-online`

Motivazione: evitare cambi non deterministici e rispettare l’approccio offline-by-default.

## Pipeline RSS (collect)

Input:
- intervallo date (date-from, date-to)
- query window `when-days`
- eventuale allowlist domini

Output:
- raw RSS XML (se online) in `reports/news_alpha/raw/rss`
- fixtures JSONL in `reports/news_alpha/collector/collector_<ts>.jsonl`
- stats JSON con conteggi e qualità

Gate opzionale:
- `--strict-dq`: fallisce se zero items “kept”.

## Pipeline run (fixtures -> DuckDB)

Input:
- fixtures JSONL
- intervallo date

Azioni:
- scoring + dedup
- mapping a ticker
- calcolo rating discreto da score medio:

  - BUY se score >= 0.20
  - DOWNGRADE se score <= -0.20
  - HOLD altrimenti

Output:
- write in `recs` (firm lane news-alpha) e `sentiment_cache`
- rejects JSONL opzionale con motivazione
- log file opzionale (plain o JSONL)

## History lane (GDELT)

Il runner include comandi `history` (download/profile/fixtures) per alimentare dataset storici,
sempre con guardrail online.

