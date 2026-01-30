# PHASE1 — DataOps

Input e configurazioni operative per:
- ingest incrementale (prezzi)
- data quality (halt-aware)
- controllo/monitoraggio (Streamlit)

## File
- `borse_chiusure_storiche.csv`: chiusure borse (ISO), include chiusure straordinarie.
- `exchange_to_market.yml`: mapping exchange -> market (coerente con `metadata.market`).
- `halts.yml`: overlay manuale (market_halts + ticker_halts) da sincronizzare su DuckDB.

## Comandi (PowerShell)
```powershell
py -m src.tools.dataops_import_closures --db data\sentinel_alpha.db
py -m src.tools.dataops_sync_halts --db data\sentinel_alpha.db

# Ingest prezzi (incrementale). Per chiamate online: --online
py -m src.tools.dataops_prices_ingest --db data\sentinel_alpha.db --asof 2024-12-31 --lookback 45 --online

# Data quality prezzi (halt-aware)
py -m src.tools.dataops_dq_prices --db data\sentinel_alpha.db --asof 2024-12-31 --window_days 365
```
