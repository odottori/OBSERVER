"""PHASE1 DataOps package.

This namespace hosts the *operational block* responsible for:
- ingest (incremental)
- calendar/halts data maintenance
- data quality (halt-aware)
- UI control room integration

It is intentionally decoupled from strategy/forecast/execution logic.
"""

from __future__ import annotations

