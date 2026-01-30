# MOD-INFRA-BASE

**Registro canonico:** [MOD-INFRA-BASE](../registry/#mod-infra-base)

- **Dominio:** Infrastruttura (prerequisiti comuni)
- **Livello:** RUN-GRADE
- **Entrypoint:** ``py scripts/sentinel.py status` / `verify``
- **Codice:** ``scripts/sentinel.py`, `src/config/*``
- **Output:** `report ambiente/config`
- **Gate minimi:** smoke + validazione config
- **Gap derivati (nota):** se instabile → drift su tutti i run

## Nota
Questa pagina è **derivata**: viene generata da `docs/010_MODULE_REGISTRY.md`.
