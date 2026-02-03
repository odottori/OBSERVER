"""Helpers for import shims (refactor tranche window).

This module centralizes the deprecation warning behavior so shims are consistent
across tranche moves. Keep it tiny and dependency-free.
"""

from __future__ import annotations

import warnings


def warn_legacy_import(old_path: str, new_path: str) -> None:
    """Emit a DeprecationWarning for a legacy import path."""
    warnings.warn(
        f"[DEPRECATED] Import path '{old_path}' is deprecated; use '{new_path}'",
        category=DeprecationWarning,
        stacklevel=3,
    )
