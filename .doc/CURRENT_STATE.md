# CURRENT_STATE — OBSERVER

Date: 2026-02-03
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
- WI-0170 (Tooling: WI Log Collector B): **CLOSED** (gates PASS).
- WI-0180 (Deprecation cleanup tranche A: src.core callers): **CLOSED** (gates PASS).
- WI-0200 (Deprecation cleanup tranche C: internal `src.db` imports): **CLOSED** (scope met; residual warnings in tranche D).
- WI-0210 (Deprecation cleanup tranche D: runtime imports ranking+sentinel): **CLOSED** (gates PASS; residual warnings moved to tranche E).
- WI-0220 (Deprecation cleanup tranche E: verify_ticker_mappings imports): **CLOSED** (gates PASS).
- WI-0230 (Deprecation cleanup tranche F: UI + entrypoints imports): **CLOSED** (gates PASS; strict DeprecationWarning gate PASS).
- WI-0240 (Tooling: one-command WI gate runner B + doc alignment): **CLOSED** (phase2).
- WI-0250 (Test suite layout: unify under tests/): **CLOSED** (gates PASS).
- WI-0260 (Tooling: Collector strict-hits + profiles): **CLOSED** (gates PASS).
- WI-0270 (Stabilizzazione EOL doc-tooling): **CLOSED** (gates PASS).
- WI-0280 (CI: GUARDIAN gate + reports artifact): **CLOSED** (gates PASS).

## Governance attiva
- Refactor fisico consentito **solo tranche-by-tranche** (1 tranche = 1 WI) con `pytest` sempre PASS.
- Update canonici solo quando esplicitamente in allowlist del WI corrente.
- Evidenze e log in `reports/` per ogni WI.
- Gate deprecation hard: usare `py -m pytest -q -W error::DeprecationWarning` come baseline.

## Workstream corrente
### Stabilizzazione (post-move) — baseline
- CI allineata ai gate locali via `scripts/guardian.py gate`.
- Gate: `py scripts/guardian.py gate --wi WI-0280 --mode normal --write-collect-log`


### WI-0115 — Skeleton tranche fisiche (TODO-only)
- Status: DONE
- Evidence: `.doc/TODO.md` (sezione WI-0115 + tranche WI-0120..0160)
- Gates: PASS (pytest/guardian) — logs: `reports/pytest_WI-0115.log`, `reports/guardian_lint_WI-0115.log`




### WI-0120 — Refactor tranche fisica: db
- Status: DONE (gates PASS — pytest 57 passed, 3 warnings; guardian PASS)
- Scope: move fisico `src/db/**` → `src/phase0/db/**` + shims + compat layer
- Evidence: `reports/2026-01-31_WI-0120_db_move.md`, `reports/2026-01-31_WI-0120_CLOSE.md`
- Gates: PASS (pytest + guardian) — logs: `reports/*_WI-0120.log`



### WI-0130 — Refactor tranche fisica: core
- Status: DONE (gates PASS — pytest 57 passed, 9 warnings; guardian PASS)
- Scope: move fisico `src/core/**` → `src/phase0/core/**` + shims + internal import hygiene
- Evidence: `reports/2026-01-31_WI-0130_core_move.md`, `reports/2026-01-31_WI-0130_CLOSE.md` (logs: `reports/*_WI-0130.log` su target machine)




### WI-0140 — Refactor tranche fisica: dataops
- Status: DONE (gates PASS — pytest PASS; guardian PASS)
- Scope: move fisico `src/dataops/**` → `src/phase0/dataops/**` + shims + fix `repo_root()` in paths
- Gates: PASS (pytest + guardian) — logs: `reports/*_WI-0140.log`
- Evidence: `reports/2026-02-01_WI-0140_dataops_move.md`, `reports/2026-02-01_WI-0140_CLOSE.md`
- Gates: pending — will produce logs `reports/*_WI-0140.log`


### WI-0150 — Refactor tranche fisica: tools
- Status: DONE (gates PASS — pytest PASS; guardian PASS)
- Scope: move fisico `src/tools/**` → `src/phase0/tools/**` + shims (`src.tools.*` → `src.phase0.tools.*`)
- Evidence: `reports/2026-02-01_WI-0150_tools_move.md`, `reports/2026-02-01_WI-0150_CLOSE.md` (logs `reports/*_WI-0150.log` su target machine)


### WI-0160 — Refactor tranche fisica: pages
- Status: DONE (gates PASS — pytest PASS; guardian PASS)
- Scope: move fisico area pages secondo Move Map + shims legacy
- Evidence: `reports/2026-02-02_WI-0160_pages_move.md`, `reports/2026-02-02_WI-0160_CLOSE.md`
- Gates: PASS (pytest + guardian) — logs: `reports/*_WI-0160.log`

### WI-0107 — Refactor Plan (virtual)
- Output canonico: `docs/012_REFACTOR_PLAN_VIRTUAL.md`
- Evidenza: `reports/2026-01-30_WI-0107_planning.md`

### Prossimi WI (sequenza consigliata)
1. WI-0170 — Tooling: WI Log Collector (B)
2. WI-0180 — Deprecation cleanup tranche A: callers `src.core.*` → `src.phase0.core.*`
3. WI-0190 — Deprecation cleanup tranche B: test imports + pages import
4. WI-0200 — Deprecation cleanup tranche C: internal `src.db.*` → `src.phase0.db.*`
5. WI-0210 — Deprecation cleanup tranche D: runtime imports ranking+sentinel
6. WI-0220 — Deprecation cleanup tranche E: verify_ticker_mappings imports
7. WI-0230 — Deprecation cleanup tranche F: UI + entrypoints imports
8. WI-0240 — Tooling: one-command WI gate runner (B)

### Tranche fisiche (DOPO WI-0107)
- WI-0120 — Refactor tranche: `db` (physical)
- WI-0130 — Refactor tranche: `core` (physical)
- WI-0140 — Refactor tranche: `dataops` (physical)
- WI-0150 — Refactor tranche: `tools` (physical)
- WI-0160 — Refactor tranche: `pages` (physical)

## Note
- Questo file è creato come baseline di governance perché l’inputpack non includeva `CURRENT_STATE/`.