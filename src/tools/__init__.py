"""DEPRECATED package shim.

Legacy import path `src.tools` is deprecated. Use `src.phase0.tools` instead.
This shim will be removed after the deprecation window closes.
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.tools", "src.phase0.tools")

# Re-export to preserve attribute access patterns.
from src.phase0.tools import *  # noqa: F401,F403
