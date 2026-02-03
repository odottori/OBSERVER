from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Repository root.

    NOTE
    ----
    This module can be moved tranche-by-tranche (e.g. `src/dataops` -> `src/phase0/dataops`).
    We therefore resolve the repo root by searching upwards for a stable sentinel file.
    """
    here = Path(__file__).resolve()
    for p in here.parents:
        # repo root contains app.py and the docs/ folder in this project
        if (p / "app.py").exists() and (p / "docs").exists():
            return p
    # Fallback: best-effort (compatible with legacy layout)
    return here.parents[3]


def default_db_path() -> Path:
    """Default DuckDB path, with env override `SENTINEL_ALPHA_DB_PATH`."""
    rr = repo_root()
    env = os.environ.get("SENTINEL_ALPHA_DB_PATH", "").strip()
    if env:
        return Path(env)
    return rr / "data" / "sentinel_alpha.db"


def dataops_dir() -> Path:
    return repo_root() / "config" / "dataops"


def closures_csv_path() -> Path:
    return dataops_dir() / "borse_chiusure_storiche.csv"


def exchange_to_market_path() -> Path:
    return dataops_dir() / "exchange_to_market.yml"


def halts_yaml_path() -> Path:
    return dataops_dir() / "halts.yml"
