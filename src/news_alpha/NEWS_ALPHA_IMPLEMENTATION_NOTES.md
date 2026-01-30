# NEWS-ALPHA Implementation Notes (v0.1)

This lane implements the **NEWS-ALPHA** pipeline per `NEWS_ALPHA_SPEC.md` v0.1.

Hard guarantees:
- **Offline by default** (no network calls).
- Writes **only** to existing DuckDB tables: `recs` and `sentiment_cache`.
- Uses a fixed firm identifier: `firm="NEWS-ALPHA"`.
- Deterministic scoring model: `model="lexicon-v1"`.

## How to run (fixtures, offline)

```bash
<PY> -m src.news_alpha.run \
  --db path/to/db.duckdb \
  --universe-id ALL \
  --date-from 2026-01-12 \
  --date-to 2026-01-13 \
  --fixtures test/fixtures/news_alpha/basic.jsonl
```

### Windows/PowerShell
In PowerShell, use the backtick (`) for line continuation.

```powershell
<PY> -m src.news_alpha.run `
  --db "./data/sentinel_alpha.db" `
  --universe-id "ALL" `
  --date-from "2026-01-12" `
  --date-to "2026-01-13" `
  --fixtures "./test/fixtures/news_alpha/basic.jsonl" `
  --log-json `
  --log-file "./report/news_alpha/news_alpha_2026-01-12_2026-01-13.jsonl"
```

### Fixtures format (JSONL)
Each line is a JSON object.

Recommended fields:
- `headline` (required)
- `published_at` (required; ISO8601)
- `ticker` (string) or `tickers` (list of strings)
- `source` (optional; default `UNKNOWN`)
- `url` (optional)
- `body` / `summary` / `description` / `content` (optional)

Example line:
```json
{"published_at":"2026-01-12T10:00:00Z","source":"Reuters","url":"https://example/a","headline":"AAPL beats expectations","tickers":["AAPL"]}
```

## Offline/Online guard

Online mode is **not used** by the v0.1 fixtures provider, but the guard is enforced to prevent accidental network usage.

Online mode requires BOTH:
- `NEWS_ALPHA_ALLOW_ONLINE=1` (environment variable)
- `--online` (CLI flag)

If you run with `--online` without setting the env allow, the command fails fast with a clear error.

## Logging

The pipeline emits structured, event-coded logs suitable for audit and troubleshooting.

### Options
- `--log-level DEBUG|INFO|WARNING|ERROR` (default: `INFO`)
- `--log-json` to emit JSONL (one JSON object per line)
- `--log-file PATH` to also write logs to a file

Notes:
- If you pass `--log-file`, NEWS-ALPHA will automatically create the parent directory if it does not exist.
- You can point `--log-file` to your existing repo “report”/“reports” folder to avoid scattering outputs.

### Event codes (non-exhaustive)
- `NEWS_ALPHA_START`: run configuration snapshot
- `NEWS_ALPHA_OFFLINE_GUARD`: emitted on guard failure
- `NEWS_ALPHA_UNIVERSE`: universe membership count
- `NEWS_ALPHA_LOAD_FIXTURES`: input rows loaded
- `NEWS_ALPHA_FILTER`: counts after universe/date filters
- `NEWS_ALPHA_SENTIMENT`: cache hits/misses and scoring counts
- `NEWS_ALPHA_DEDUP`: within-run dedup counts
- `NEWS_ALPHA_AGG`: number of (date,ticker) outputs
- `NEWS_ALPHA_DB_WRITE`: DB writes summary
- `NEWS_ALPHA_SUMMARY`: final run summary

Each event includes a `run_id` so a single run is reconstructible end-to-end.

## Deterministic sentiment model (lexicon-v1)

- Score is computed from `headline` + optional `body`.
- Normalization: trim, collapse whitespace, lowercase.
- Tokenization: `[A-Za-z]+`.
- Scoring:

```
score = (pos - neg) / (pos + neg)  if (pos+neg) > 0 else 0.0
```

Score is clipped to `[-1.0, +1.0]`.

### Caching (`sentiment_cache`)
- `text_hash` = SHA-256 hex over the normalized text.
- `model` = `lexicon-v1`.
- NEWS-ALPHA reads existing cache values first, then inserts only cache misses (unless `--overwrite`).

#### Schema compatibility
NEWS-ALPHA writes only to existing tables and does not run migrations. Some repositories may have minor column-name variations.

Supported score column names:
- In `sentiment_cache`: `sentiment_score` (canonical), `sentiment`, `score`, or `value`.
- In `recs`: `sentiment_score` (canonical), `sentiment`, or `score`.

If none of the supported score columns are present, NEWS-ALPHA fails fast with a clear error listing the detected columns.

Schema note: some repos may use a non-canonical score column name in `sentiment_cache`.
NEWS-ALPHA will write/read the first matching column among: `sentiment_score`, `sentiment`, `score`, `value`.

## Ticker normalization
- Trim + uppercase.
- Class-share dot notation for the narrow pattern `^[A-Z]{1,5}-[A-Z]$`:
  - `BRK-B` -> `BRK.B`

## Dedup and aggregation

### Dedup (within run)
- Primary: URL (exact match)
- Fallback: `sha256(published_at|source|headline)`

Winner selection on collisions is deterministic (prefer longer text, then lexicographic URL/headline).

### Aggregation
- One output row per `(date, ticker)` where `date` is derived from `published_at` (UTC date).
- `sentiment_score` is the **mean** of article scores for the group, clipped to `[-1, +1]`.
- Representative `headline/source_url/published_at`: the article with max absolute sentiment; tie-break by lexicographic URL.

## Rating mapping
- score `>= +0.20`  -> `BUY`
- `-0.20 < score < +0.20` -> `HOLD`
- score `<= -0.20` -> `DOWNGRADE`

## Idempotency

- Default mode avoids writing duplicate keys in `recs` by skipping existing `(date, ticker)` rows for `firm="NEWS-ALPHA"`.
- `--overwrite` deletes existing `firm` rows in the date range before inserting.


## Optional: Observer (post-run QA)

A lightweight observer is provided to sanity-check the **outputs** (and optionally the logs).

```bash
<PY> -m src.news_alpha.observer --db path/to/db.duckdb --log-file runs/news_alpha.log
```

It prints a single verdict (`OK|WARN|FAIL`) and a list of issues.

The observer is deterministic and offline; it does not call any network services.
