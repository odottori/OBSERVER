"""Legacy import shim.

Canonical module:
    - src.phase0.db.migrate

Keeps the stable entrypoint:
    py -m src.db.migrate
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.db.migrate", "src.phase0.db.migrate")

from src.phase0.db.migrate import *  # noqa: F401,F403


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="SENTINEL-ALPHA DuckDB schema migration")
    p.add_argument("--db", default="data/sentinel_alpha.db", help="Path to DuckDB database file")
    args = p.parse_args()

    cli_migrate(args.db)  # type: ignore[name-defined]
    print(f"[+] Migration completed: {args.db}")
