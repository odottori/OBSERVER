# CHANGELOG — OBSERVER v1.2.5 (PHASE1 DataOps)

Date: 2026-01-30

## Canonical docs (updated)
- `docs/002_PDR_OBSERVER.md`
  - PHASE1 DataOps scope aligned to checkpoint + FR-09.
  - Added PHASE1 DoD and operational notes.
- `docs/004_DDT_DATADICTIONARY.md`
  - Added PHASE1 DataOps tables: `dq_runs`, `dq_findings`, `dq_metrics_daily`.
- `docs/005_TRACEABILITY_MATRIX.md`
  - Added PHASE1 DataOps trace block (B2) + Streamlit page `11_DataOps_Control_Room.py`.
  - Normalized command examples to use forward slashes (LaTeX-safe) for `.doc/...` paths.
- `docs/010_MODULE_REGISTRY.md`
  - Registered module `MOD-DATAOPS`.
- `docs/000_README_DOCSET.md`, `docs/008_EVIDENCE_PACK.md`
  - Normalized example paths to `scripts/` and `data/sentinel_alpha.db` (LaTeX-safe + cross-platform).

## Docset artifacts (regenerated)
- `docs/OBSERVER_v1.2.5.md`
  - Regenerated via `scripts/build_master_md.py` from canonical docs + `docs/specs/`.
- `docs/OBSERVER_v1.2.5.pdf`
  - Regenerated from the LaTeX clean project (`docs/LATEX_zip/OBSERVER_LATEX_CLEAN_v1.2.5_PROJECT.zip`) using Pandoc + pdfLaTeX.

## PHASE1 tests (added) + evidence
- Added:
  - `test/test_phase1_dataops_schema.py`
  - `test/test_phase1_dataops_dq_prices.py`
- Evidence:
  - `reports/pytest_phase1.log` (2 tests PASS)

## Phase2 governance (WI-0106)
- `docs/002_PDR_OBSERVER.md`
  - Added delivery taxonomy Phase0/Phase1/Phase2 + DoD + entrypoint snapshot + release policy (NODATA/WITH_DB).
- `docs/004_DDT_DATADICTIONARY.md`
  - Added DB surface by phase + DB required matrix (tools/pages) + canonical DB artifacts/path rules.
- `docs/005_TRACEABILITY_MATRIX.md`
  - Added “vista per fasi” (Phase taxonomy) + cluster PHASE2_EXECUTION summary.
- `docs/010_MODULE_REGISTRY.md`
  - Added `Phase` tag to every `MOD-*` (PHASE0/PHASE1/PHASE2/UI/SIGNAL).
- `docs/OBSERVER_v1.2.5.md`
  - Refreshed embedded canonical sections to match updated canonici.
- `requirements.txt`
  - Added reproducible baseline deps (duckdb/pandas/numpy/streamlit/pytest/etc.).

## Refactor governance (WI-0107 — planning-only)
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`
  - Added Move Map (virtual) by tranche: `db/core/dataops/tools/pages`.
  - Added import-shims strategy + deprecation policy + rollback plan.
  - Added gate toolkit (G0..G3) and expected log naming.
- `docs/000_README_DOCSET.md`
  - Added governance note: refactor fisico consentito solo tranche-by-tranche dopo piano virtuale.
- `scripts/build_master_md.py`
  - Included `012_REFACTOR_PLAN_VIRTUAL.md` in CANON build list.
- `.doc/TODO.md`
  - Added WI-0107 + sub-WIs 0110..0115 and physical tranche placeholders 0120..0160.
- `.doc/CURRENT_STATE.md`, `.doc/LOGBOOK.md`
  - Created as **real files** (baseline governance) because the provided inputpack did not include prior versions.
- `reports/2026-01-30_WI-0107_planning.md`
  - Added evidence record for planning milestone.

Constraints respected:
- No changes to `src/**` and `tests/**` (planning-only).


## Move Map final (WI-0111 — virtual)

- `reports/WI-0111_move_map.md`
  - Added tranche Move Map (pattern-based) for WI-0120..0160: `db/core/dataops/tools/pages`.
  - Added expected log naming for WI-0111 gates.
- `docs/012_REFACTOR_PLAN_VIRTUAL.md`
  - Linked/embedded tranche table for Move Map final (WI-0111).
- `.doc/TODO.md`
  - Expanded WI-0111 allowlist to include governance files (`.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`).
- `.doc/LOGBOOK.md`, `.doc/CURRENT_STATE.md`
  - Recorded WI-0111 DONE state (gates PASS) and evidence pointer (`reports/*_WI-0111.log`).

Constraints respected:
- No changes to `src/**` and `tests/**` (planning-only).
