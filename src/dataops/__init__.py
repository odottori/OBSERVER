"""Legacy package import shim.

Canonical package:
    - src.phase0.dataops

This package remains temporarily to preserve stable imports during tranche moves.
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops", "src.phase0.dataops")

from src.phase0.dataops import *  # noqa: F401,F403
