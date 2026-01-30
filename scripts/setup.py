"""SENTINEL-ALPHA bootstrap / repair entrypoint (cross-platform).

This script is intentionally stdlib-only so it can run on a fresh machine.

What it does
------------
- Create or repair a local Python virtual environment (.venv)
- Install requirements.txt
- Ensure folder layout (data/, reports/, logs/, config/)
- Create/upgrade the DuckDB schema (idempotent migrations)
- Optionally run tests and/or the full certify pipeline

Examples
--------
<PY> scripts/setup.py init
<PY> scripts/setup.py repair --db data/sentinel_alpha.db
<PY> scripts/setup.py reset --certify

okkio questo e' un file importante

"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("[cmd]", " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def ensure_dirs(root: Path) -> None:
    for d in ("data", "reports", "logs", "config"):
        (root / d).mkdir(parents=True, exist_ok=True)


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def create_or_recreate_venv(root: Path, mode: str) -> Path:
    venv_dir = root / ".venv"
    py = venv_python(root)

    if mode == "reset" and venv_dir.exists():
        bak = root / f".venv.bak_{stamp()}"
        print(f"Backing up existing .venv -> {bak}")
        shutil.move(str(venv_dir), str(bak))

    if not py.exists():
        run([sys.executable, "-m", "venv", ".venv"], cwd=root)

    if not py.exists():
        raise RuntimeError(f"Failed to create .venv (expected {py})")
    return py


def write_local_env_file(
    root: Path,
    db_rel: str,
    provider_order: str,
    backfill: str,
    disable_yf: str,
    av_key: str,
) -> None:
    """Create config/sentinel.local.env if missing.

    The runner (scripts/sentinel.py) auto-loads this file in a shell-agnostic way.
    This repository standardizes on KEY=value, not shell scripts.

    NOTE: this file is safe to commit because it contains no secrets by default.
    """

    cfg = root / "config" / "sentinel.local.env"
    if cfg.exists():
        return

    lines = [
        "# Auto-generated local configuration for SENTINEL-ALPHA",
        "# Format: KEY=value (shell-agnostic).",
        "# This file is loaded by scripts/sentinel.py if present.",
        "",
        f"SENTINEL_ALPHA_DB_PATH={db_rel}",
        f"SENTINEL_PRICE_PROVIDER_ORDER={provider_order}",
        f"SENTINEL_ALLOW_ONLINE_BACKFILL={backfill}",
        f"SENTINEL_DISABLE_YFINANCE={disable_yf}",
        f"ALPHAVANTAGE_API_KEY={av_key}",
        "",
    ]
    cfg.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="setup", description="SENTINEL-ALPHA bootstrap")
    ap.add_argument("mode", nargs="?", choices=["init", "repair", "reset", "doctor"], default="init")
    ap.add_argument("--db", dest="db_path", default="data/sentinel_alpha.db")
    ap.add_argument("--provider-order", default="stooq")
    ap.add_argument("--enable-yfinance", action="store_true")
    ap.add_argument("--no-backfill", action="store_true")
    ap.add_argument("--alphavantage-key", default="")
    ap.add_argument("--certify", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    root = project_root()
    ensure_dirs(root)

    db = Path(args.db_path)
    if not db.is_absolute():
        db = root / db

    py = create_or_recreate_venv(root, args.mode)

    # Install deps
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=root)
    run([str(py), "-m", "pip", "install", "-r", "requirements.txt"], cwd=root)
    run([str(py), "-m", "pip", "check"], cwd=root)

    # Config helper (shell-agnostic)
    backfill = "0" if args.no_backfill else "1"
    disable_yf = "0" if args.enable_yfinance else "1"
    write_local_env_file(
        root=root,
        db_rel=args.db_path,
        provider_order=args.provider_order,
        backfill=backfill,
        disable_yf=disable_yf,
        av_key=args.alphavantage_key,
    )

    # Apply env for the commands executed by THIS script
    env = os.environ.copy()
    env["SENTINEL_ALPHA_DB_PATH"] = str(db)
    env["SENTINEL_PRICE_PROVIDER_ORDER"] = args.provider_order
    env["SENTINEL_ALLOW_ONLINE_BACKFILL"] = backfill
    env["SENTINEL_DISABLE_YFINANCE"] = disable_yf
    if args.alphavantage_key:
        env["ALPHAVANTAGE_API_KEY"] = args.alphavantage_key

    # DB migrations (idempotent)
    run([str(py), "-m", "src.db.migrate", "--db", str(db)], cwd=root)

    if args.mode != "doctor" and not args.skip_tests:
        run([str(py), "main_test.py"], cwd=root)

    if args.certify:
        run([str(py), str(root / "scripts" / "sentinel.py"), "certify", "--db", str(db)], cwd=root)

    print("\nDone")
    print(f"DB: {db}")


if __name__ == "__main__":
    main()
