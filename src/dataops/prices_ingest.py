"""Legacy import shim.

Canonical module:
    - src.phase0.dataops.prices_ingest
"""

from __future__ import annotations

from src.compat.shims import warn_legacy_import as _warn_legacy_import

_warn_legacy_import("src.dataops.prices_ingest", "src.phase0.dataops.prices_ingest")

from src.phase0.dataops.prices_ingest import *  # noqa: F401,F403
