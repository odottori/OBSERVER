# MOD-DB-SCHEMA

**Registro canonico:** [MOD-DB-SCHEMA](../registry/#mod-db-schema)

- **Dominio:** Infrastruttura (DB)
- **Livello:** RUN-GRADE
- **Entrypoint:** ``py scripts/sentinel.py migrate``
- **Codice:** ``src/db/migrate.py``
- **Output:** `schema tabelle core`
- **Gate minimi:** migrate + schema checks
- **Gap derivati (nota):** blocca ingestione/segnali/esecuzione se schema non stabile

## Nota
Questa pagina è **derivata**: viene generata da `docs/010_MODULE_REGISTRY.md`.
