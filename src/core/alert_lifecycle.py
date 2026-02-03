"""Legacy import shim.

Canonical module:
    - src.phase0.core.alert_lifecycle
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.core.alert_lifecycle", "src.phase0.core.alert_lifecycle")

from src.phase0.core.alert_lifecycle import *  # noqa: F401,F403
