"""DEPRECATED module shim.

Legacy import path `src.tools.forecast_rankings` is deprecated. Use `src.phase0.tools.forecast_rankings` instead.
This shim will be removed after the deprecation window closes.
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.tools.forecast_rankings", "src.phase0.tools.forecast_rankings")

# Preserve `import src.tools.forecast_rankings` semantics.
from src.phase0.tools.forecast_rankings import *  # noqa: F401,F403

def _run_as_module() -> None:
    """Run the new module as `__main__` (preserves `py -m src.tools.forecast_rankings`)."""
    import runpy as _runpy
    _runpy.run_module("src.phase0.tools.forecast_rankings", run_name="__main__")

if __name__ == "__main__":
    _run_as_module()
