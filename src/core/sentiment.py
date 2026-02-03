"""Legacy import shim.

Canonical module:
    - src.phase0.core.sentiment
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.core.sentiment", "src.phase0.core.sentiment")

from src.phase0.core.sentiment import *  # noqa: F401,F403
