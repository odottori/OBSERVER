"""Legacy import shim.

Canonical module:
    - src.phase0.core.ticker_normalize
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.core.ticker_normalize", "src.phase0.core.ticker_normalize")

from src.phase0.core.ticker_normalize import *  # noqa: F401,F403
