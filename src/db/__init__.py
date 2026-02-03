"""Legacy DB utilities (DuckDB) — import shim.

Canonical location:
    - src.phase0.db

This package remains as a shim during the deprecation window defined in
docs/012_REFACTOR_PLAN_VIRTUAL.md.
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.db", "src.phase0.db")
