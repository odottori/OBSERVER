import os
from dataclasses import dataclass
import duckdb


@dataclass(frozen=True)
class DbConfig:
    """DuckDB connection configuration."""

    db_path: str = os.path.join("data", "sentinel_alpha.db")


def connect(cfg: DbConfig | None = None) -> duckdb.DuckDBPyConnection:
    """Create a DuckDB connection.

    Keeping this in a single place lets us standardize settings (threads, pragmas)
    without scattering them across the codebase.
    """

    cfg = cfg or DbConfig()
    con = duckdb.connect(database=cfg.db_path)
    # Conservative defaults (can be tuned later)
    try:
        con.execute("PRAGMA enable_progress_bar=false")
    except Exception:
        pass
    return con
