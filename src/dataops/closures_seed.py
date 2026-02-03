"""Legacy import shim.

Canonical module:
    - src.phase0.dataops.closures_seed
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops.closures_seed", "src.phase0.dataops.closures_seed")

from src.phase0.dataops.closures_seed import *  # noqa: F401,F403
