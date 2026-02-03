"""Legacy import shim.

Canonical module:
    - src.phase0.dataops.paths
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops.paths", "src.phase0.dataops.paths")

from src.phase0.dataops.paths import *  # noqa: F401,F403
