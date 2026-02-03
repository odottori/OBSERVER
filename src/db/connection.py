"""Legacy import shim.

Canonical module:
    - src.phase0.db.connection
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.db.connection", "src.phase0.db.connection")

from src.phase0.db.connection import *  # noqa: F401,F403
