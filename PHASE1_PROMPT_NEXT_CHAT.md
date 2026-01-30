# Prompt per continuare e chiudere PHASE1

Incolla questo prompt in una nuova chat (insieme allo ZIP checkpoint).

---

Ho uno ZIP del progetto OBSERVER con PHASE1 DataOps parzialmente implementata.
Nel repo sono già presenti:
- config/dataops/borse_chiusure_storiche.csv
- config/dataops/exchange_to_market.yml
- config/dataops/halts.yml
- src/dataops/closures_seed.py
- src/dataops/halts_sync.py
- src/dataops/prices_ingest.py
- scripts/phase01_dataops/_reference/EXEC_Download_REFERENCE.py
- scripts/phase01_dataops/_reference/EXEC_DataQuality_REFERENCE.py

Obiettivo: chiudere PHASE1 completamente con UI+docs+tests+PDF+ZIP finale.

Task obbligatori:
1) Implementare src/dataops/dq_prices.py (DQ prezzi halt-aware) e scrivere su tabelle DQ.
2) Patchare src/db/migrate.py aggiungendo (idempotente) dq_runs, dq_findings, dq_metrics_daily.
3) Creare tool CLI in src/tools/: dataops_import_closures, dataops_sync_halts, dataops_prices_ingest, dataops_dq_prices, dataops_status.
4) Aggiungere Streamlit: pages/11_DataOps_Control_Room.py con:
   - editor halts.yml (save)
   - bottoni (import closures, sync halts, ingest prices, run dq)
   - viste su data_gaps e tabelle DQ.
5) Aggiornare canonici e mkdocs raggruppando moduli per fase (PHASE1, PHASE2...): Module Registry, Data Dictionary, Traceability, Evidence Pack.
6) Fixare scripts/build_all_docs.py se rotto.
7) Rigenerare docs/OBSERVER_v1.2.5.md e il PDF v1.2.5 (LaTeX clean project) in modo chirurgico e coerente coi canonici.
8) Aggiungere test PHASE1 e far girare pytest; salvare log evidenza.
9) Generare ZIP finale pronto per download e una lista di file/feature obsoleti da rimuovere.

Procedi senza ulteriori domande: implementa, testa, rigenera PDF e consegna lo ZIP finale.
