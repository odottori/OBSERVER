"""Legacy import shim.

Canonical module:
    - src.phase0.db.audit_store
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.db.audit_store", "src.phase0.db.audit_store")

from src.phase0.db.audit_store import *  # noqa: F401,F403
