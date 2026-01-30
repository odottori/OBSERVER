from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Repository root (two levels above `src/`)."""
    return Path(__file__).resolve().parents[2]


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
