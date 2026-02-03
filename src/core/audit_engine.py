"""Legacy import shim.

Canonical module:
    - src.phase0.core.audit_engine
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.core.audit_engine", "src.phase0.core.audit_engine")

from src.phase0.core.audit_engine import *  # noqa: F401,F403
