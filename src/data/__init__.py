"""Data acquisition helpers.

This package hosts optional ingestion and backfill utilities.
Audit logic must NOT depend on network availability; therefore every module
here is designed to be:
- optional (can be disabled)
- bounded (timeouts, max windows)
- auditable (records attempts into DuckDB)
"""
