# DDT — Operational Data Dictionary

> GENERATED FILE — DO NOT EDIT  
> Source of truth: `./docs/`  
> Generated: 2026-02-04T07:14:17Z  
> Fingerprint: 3ca08cf18ee7e88f

## Sources
- `docs/004_DDT_DATADICTIONARY.md`

---
### Colonne

| Colonna | Tipo | NULL? | Semantica |
|---|---|---|---|
| ticker | VARCHAR | NO | Ticker canonico interno (chiave primaria). |
| sector | VARCHAR | YES | Settore economico (granularita’ libera). |
| market | VARCHAR | YES | Etichetta mercato/regione (es. US, EU, ITALY). |
| currency | VARCHAR | YES | Valuta di quotazione (ISO-4217, es. USD, EUR). |
| is_tobin_tax | BOOLEAN | YES | Flag: applica Tobin/FTT (Italia) come costo transazione addizionale. |
| yf_symbol | VARCHAR | YES | Simbolo provider yfinance (se diverso dal ticker canonico). |
| stooq_symbol | VARCHAR | YES | Simbolo provider stooq (se diverso dal ticker canonico). |
| instrument_type | VARCHAR | YES | Classe strumento (EQUITY, ETF, DERIVATIVE, ...). |
| ftt_rate | DOUBLE | YES | Aliquota FTT come frazione del notional (es. 0.001 = 0.10%). |


### Vincoli (DuckDB)

- NOT NULL: NOT NULL
- PRIMARY KEY: PRIMARY KEY(ticker)


## Practical DuckDB Queries (template)

> Aggiorna nei canonici di progetto e rigenera con `guardian derive`.

- Elenco tabelle:
  - `SHOW TABLES;`
- Schema tabella:
  - `DESCRIBE <table_name>;`
- Conteggio righe e range date:
  - `SELECT MIN(date), MAX(date), COUNT(*) FROM <table>;`
