"""Legacy import shim.

Canonical module:
    - src.phase0.dataops.common
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops.common", "src.phase0.dataops.common")

from src.phase0.dataops.common import *  # noqa: F401,F403
