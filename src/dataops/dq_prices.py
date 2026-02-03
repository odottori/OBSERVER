"""Legacy import shim.

Canonical module:
    - src.phase0.dataops.dq_prices
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops.dq_prices", "src.phase0.dataops.dq_prices")

from src.phase0.dataops.dq_prices import *  # noqa: F401,F403
