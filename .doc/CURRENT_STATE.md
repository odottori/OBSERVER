# CURRENT_STATE — OBSERVER

Date: 2026-01-30
Repo canonico operativo: `OBSERVER_v1.2.5_PHASE1_FINAL`

## Snapshot
- PHASE1: **CLOSED** (docs/pdf/master rigenerati; `pytest` PASS) — per contesto.
- WI-0106 (docs-enabled): **DONE** (PDR/DDT/Traceability/Module Registry aggiornati; guardian lint PASS).
- WI-0104 (refactor fisico per fasi): **BLOCKED** come esecuzione “in blocco”.
- WI-0107 (Refactor Plan, virtual): **DELIVERED (planning milestone)** — nessun move in `src/`.
- WI-0110 (Inventory & boundary map, virtual): **DONE**.
- WI-0111 (Move Map final, virtual): **DONE** (gates PASS; logs in `reports/*_WI-0111.log`).
- WI-0112 (Import shims plan + deprecation policy): **DONE** (gates PASS; evidence in `reports/WI-0112_shims_policy.md`).
- WI-0113 (Rollback plan, virtual): **DONE** (gates PASS; logs in `reports/*_WI-0113.log`).
- WI-0114 (Gate protocol + expected logs, virtual): **DONE** (gates PASS; logs in `reports/*_WI-0114.log`).
- WI-0115 (Skeleton tranche fisiche, TODO-only): **DONE** (gates PASS; logs in `reports/*_WI-0115.log`).

## Governance attiva
- Refactor fisico consentito **solo tranche-by-tranche** (1 tranche = 1 WI) con `pytest` sempre PASS.
- Update canonici solo quando esplicitamente in allowlist del WI corrente.
- Evidenze e log in `reports/` per ogni WI.

## Workstream corrente
### WI-0115 — Skeleton tranche fisiche (TODO-only)
- Status: DONE
- Evidence: `.doc/TODO.md` (sezione WI-0115 + tranche WI-0120..0160)
- Gates: PASS (pytest/guardian) — logs: `reports/pytest_WI-0115.log`, `reports/guardian_lint_WI-0115.log`



### WI-0107 — Refactor Plan (virtual)
- Output canonico: `docs/012_REFACTOR_PLAN_VIRTUAL.md`
- Evidenza: `reports/2026-01-30_WI-0107_planning.md`

### Prossimi WI (sequenza consigliata)
1. WI-0120..0160 — Tranche fisiche (esecuzione tranche-by-tranche)

### Tranche fisiche (DOPO WI-0107)
- WI-0120 — Refactor tranche: `db` (physical)
- WI-0130 — Refactor tranche: `core` (physical)
- WI-0140 — Refactor tranche: `dataops` (physical)
- WI-0150 — Refactor tranche: `tools` (physical)
- WI-0160 — Refactor tranche: `pages` (physical)

## Note
- Questo file è creato come baseline di governance perché l’inputpack non includeva `CURRENT_STATE/`.
