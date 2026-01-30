# CURRENT_STATE — OBSERVER

Date: 2026-01-30
Repo canonico operativo: `OBSERVER_v1.2.5_PHASE1_FINAL`

## Snapshot
- PHASE1: **CLOSED** (docs/pdf/master rigenerati; `pytest` PASS) — per contesto.
- WI-0106 (docs-enabled): **DONE** (PDR/DDT/Traceability/Module Registry aggiornati; guardian lint PASS).
- WI-0104 (refactor fisico per fasi): **BLOCKED** come esecuzione “in blocco”.
- WI-0107 (Refactor Plan, virtual): **DELIVERED (planning milestone)** — nessun move in `src/` - gates executed + logs present.

## Governance attiva
- Refactor fisico consentito **solo tranche-by-tranche** (1 tranche = 1 WI) con `pytest` sempre PASS.
- Update canonici solo quando esplicitamente in allowlist del WI corrente.
- Evidenze e log in `reports/` per ogni WI.

## Workstream corrente
### WI-0107 — Refactor Plan (virtual)
- Output canonico: `docs/012_REFACTOR_PLAN_VIRTUAL.md`
- Evidenza: `reports/2026-01-30_WI-0107_planning.md`

### Prossimi WI (sequenza consigliata)
1. WI-0110 — Inventory & boundary map (virtual)
2. WI-0111 — Move Map final (virtual)
3. WI-0112 — Import shims plan + deprecation policy
4. WI-0113 — Rollback plan (finalizzazione)
5. WI-0114 — Gate protocol + expected logs (finalizzazione)
6. WI-0115 — Skeleton tranche fisiche (TODO-only)

### Tranche fisiche (DOPO WI-0107)
- WI-0120 — Refactor tranche: `db` (physical)
- WI-0130 — Refactor tranche: `core` (physical)
- WI-0140 — Refactor tranche: `dataops` (physical)
- WI-0150 — Refactor tranche: `tools` (physical)
- WI-0160 — Refactor tranche: `pages` (physical)

## Note
- Questo file è creato come baseline di governance perché l’inputpack non includeva `CURRENT_STATE/`.
