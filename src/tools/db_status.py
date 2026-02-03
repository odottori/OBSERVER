"""DEPRECATED module shim.

Legacy import path `src.tools.db_status` is deprecated. Use `src.phase0.tools.db_status` instead.
This shim will be removed after the deprecation window closes.
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.tools.db_status", "src.phase0.tools.db_status")

# Preserve `import src.tools.db_status` semantics.
from src.phase0.tools.db_status import *  # noqa: F401,F403

def _run_as_module() -> None:
    """Run the new module as `__main__` (preserves `py -m src.tools.db_status`)."""
    import runpy as _runpy
    _runpy.run_module("src.phase0.tools.db_status", run_name="__main__")

if __name__ == "__main__":
    _run_as_module()
