"""Legacy import shim.

Canonical module:
    - src.phase0.core.tax_model
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.core.tax_model", "src.phase0.core.tax_model")

from src.phase0.core.tax_model import *  # noqa: F401,F403
