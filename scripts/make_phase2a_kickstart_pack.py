# scripts/make_phase2a_kickstart_pack.py
# Create a Phase2-A kickstart ZIP from the current repo:
# - excludes .venv, caches, .git, pyc, etc.
# - by default excludes data/ (use --include-db to include it)
# - optionally embeds PHASE2A_PROMPT.md + manifest inside the ZIP (no repo files created)

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import zipfile
from pathlib import Path


DEFAULT_EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
}
DEFAULT_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".pyd", ".so", ".dll"}
DEFAULT_EXCLUDE_FILES = {".DS_Store"}


PHASE2A_PROMPT_TEMPLATE = """\
CONTESTO
- OBSERVER: PHASE1 chiusa e stabile; canonici aggiornati; master docs rigenerato.
- Ora avviamo PHASE2-A: “Research & Backtest Engine v1” con scope ridotto e consegnabile.

OBIETTIVO PHASE2-A (v1)
- Asset class: solo strumenti già presenti in prices (ETF/equities), niente derivati.
- Prezzi: daily close (o settle) → returns close-to-close.
- Corporate actions: non implementate in v1 a meno che ingestion abbia adjusted prices.
  In v1: regola esplicita + guardrail (split-like jump → flag).
- Valuta base: EUR (o native se tutto EUR) → esplicito nel dataset.
- Costi/slippage: modello semplice (commission + bps) parametrico.
- Output: report performance + trade log + KPI, riproducibile.

REGOLE
- 1 WI per volta, atomico.
- Ogni WI deve produrre: code + test + log evidenza + update canonici (solo se in allowlist del WI).
- Windows/PowerShell usa `py`.
- Niente “big bang”: tranche piccole, gates ripetibili.
- Se manca info: scelta ragionevole + log in CHANGELOG.

DELIVERABLE FINALI
1) `py -m src.tools.research_build_dataset ...` genera dataset canonico deterministico (DuckDB o parquet).
2) `py -m src.tools.bt_run ...` produce:
   - trades
   - posizioni giornaliere
   - equity curve + metrics
   - report (md o html) in `reports/`
3) `pytest` verde + log in `reports/pytest_phase2.log`
4) Canonici aggiornati: DDT + Module Registry + Traceability + master docs rigenerato (bump versione se necessario)

SPEC PHASE2-A
- Incolla/Allega PHASE2A_SPEC.md (se presente).
"""


def _is_excluded(path: Path, repo_root: Path, include_db: bool) -> bool:
    rel = path.relative_to(repo_root)

    # Exclude directories (anywhere in path)
    for part in rel.parts[:-1]:
        if part in DEFAULT_EXCLUDE_DIRS:
            return True

    # Exclude data/ unless requested
    if not include_db and rel.parts and rel.parts[0] == "data":
        return True

    # Exclude file names / suffixes
    if path.name in DEFAULT_EXCLUDE_FILES:
        return True
    if path.suffix.lower() in DEFAULT_EXCLUDE_SUFFIXES:
        return True

    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Phase2-A kickstart zip (no venv, no caches).")
    ap.add_argument(
        "--root",
        default=".",
        help="Repo root (default: current directory). Run from repo root for best results.",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Output zip path. Default: ./OBSERVER_PHASE2A_KICKSTART_<timestamp>_{NODATA|WITH_DB}.zip",
    )
    ap.add_argument(
        "--include-db",
        action="store_true",
        help="Include data/ (e.g., sentinel_alpha.db). Default: excluded.",
    )
    ap.add_argument(
        "--spec",
        default=None,
        help="Optional path to PHASE2A spec markdown to embed in zip as PHASE2A_SPEC.md",
    )
    ap.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not embed PHASE2A_PROMPT.md in the zip.",
    )
    args = ap.parse_args()

    repo_root = Path(args.root).resolve()
    if not repo_root.exists():
        print(f"ERROR: root does not exist: {repo_root}", file=sys.stderr)
        return 2

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = "WITH_DB" if args.include_db else "NODATA"
    out_path = Path(args.out).resolve() if args.out else (repo_root / f"OBSERVER_PHASE2A_KICKSTART_{ts}_{tag}_NO_VENV.zip")

    spec_path = Path(args.spec).resolve() if args.spec else None
    if spec_path and not spec_path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 2

    # Collect files
    files: list[Path] = []
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        if _is_excluded(p, repo_root, include_db=args.include_db):
            continue
        files.append(p)

    files.sort(key=lambda x: str(x.relative_to(repo_root)).lower())

    # Build zip
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    manifest_lines = []
    manifest_lines.append("== PHASE2A KICKSTART PACK ==")
    manifest_lines.append(f"root: {repo_root}")
    manifest_lines.append(f"created_at: {dt.datetime.now().isoformat(timespec='seconds')}")
    manifest_lines.append(f"include_db: {bool(args.include_db)}")
    if spec_path:
        manifest_lines.append(f"spec_embedded_from: {spec_path}")
    manifest_lines.append("")
    manifest_lines.append("FILES:")
    for p in files:
        rel = p.relative_to(repo_root).as_posix()
        manifest_lines.append(rel)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # repo files
        for p in files:
            rel = p.relative_to(repo_root).as_posix()
            zf.write(p, arcname=rel)

        # embedded prompt + manifest (no repo writes)
        if not args.no_prompt:
            zf.writestr("PHASE2A_PROMPT.md", PHASE2A_PROMPT_TEMPLATE)

        zf.writestr("PACK_MANIFEST.txt", "\n".join(manifest_lines) + "\n")

        if spec_path:
            zf.write(spec_path, arcname="PHASE2A_SPEC.md")

    print(f"OK: wrote {out_path}")
    print(f"OK: files_included={len(files)} include_db={bool(args.include_db)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
