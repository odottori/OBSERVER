"""Legacy import shim.

Canonical module:
    - src.phase0.dataops.halts_sync
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops.halts_sync", "src.phase0.dataops.halts_sync")

from src.phase0.dataops.halts_sync import *  # noqa: F401,F403
