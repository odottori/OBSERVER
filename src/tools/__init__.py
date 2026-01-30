"""Utility tools / diagnostics for SENTINEL-ALPHA.

This package contains command-line helpers that operate on the DuckDB database.

Design rules
------------
- Tools are safe to run against production / audit databases.
- Tools must be defensive about schema evolution (older DBs may miss columns).
- Tools must not hardcode absolute paths or run_ids.
"""
