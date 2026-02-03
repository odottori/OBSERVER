"""Schema definition and migrations.

SENTINEL-ALPHA uses DuckDB as the single source of truth.

Design goals
------------
- One canonical schema owner (this module)
- Backwards-compatible migrations against existing local DBs
- Deterministic seeding for the *current* local universe (no forced provider changes)

Institutional audit extensions
------------------------------
This schema includes the primitives required to produce certification-grade
backtests:
- Dynamic universes + historical membership (survivorship-bias control)
- Time-bounded ticker mappings (symbol changes / corporate actions)
- Trading halts (ticker-level and market-level) to model execution feasibility
- Sentiment cache (local, deterministic) for repeatable scoring
- Optional decision ledger for skipped/shifted signals

Version: 2.1.0 - Added sentiment cache table for NEWS-ALPHA integration
Last updated: 2026-01-16

NOTE
----
SENTINEL-ALPHA does not ship licensed index constituent datasets.
You populate `universe_membership` from your source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class UniverseSeed:
    universe_id: str
    name: str
    market: str
    description: str


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    q = "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?"
    return con.execute(q, [table]).fetchone()[0] > 0


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    if not _table_exists(con, table):
        return set()
    rows = con.execute(f"PRAGMA table_info('{table}')").fetchall()
    return {r[1] for r in rows}  # name is column index 1


def _add_column_if_missing(con: duckdb.DuckDBPyConnection, table: str, col: str, ddl: str) -> None:
    cols = _columns(con, table)
    if col in cols:
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create missing tables and add missing columns.

    Safe to run multiple times.
    """

    # ---------------------------------------------------------------------
    # Core tables
    # ---------------------------------------------------------------------
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            ticker VARCHAR PRIMARY KEY,
            sector VARCHAR,
            market VARCHAR,          -- e.g., 'US', 'EU', 'ITALY'
            currency VARCHAR,
            instrument_type VARCHAR, -- e.g., 'EQUITY', 'ETF', 'DERIVATIVE'
            is_tobin_tax BOOLEAN DEFAULT FALSE,
            ftt_rate DOUBLE,         -- optional; fraction of notional (e.g., 0.001 = 0.10%)
            yf_symbol VARCHAR,
            stooq_symbol VARCHAR
        );

        CREATE TABLE IF NOT EXISTS prices (
            date DATE,
            ticker VARCHAR,
            price DOUBLE,        -- close
            open_price DOUBLE,   -- open (if available)
            source VARCHAR,      -- provenance of the price row (e.g., 'legacy', 'yfinance', 'stooq')
            fetched_at TIMESTAMP,-- when this row was fetched/inserted
            PRIMARY KEY(date, ticker)
        );

        -- Corporate actions / dividends (retail realism)
        -- NOTE: v0 schema only; cashflow application is introduced incrementally in A7.x.
        CREATE TABLE IF NOT EXISTS dividends (
            ticker VARCHAR,
            ex_date DATE,
            pay_date DATE,
            amount DOUBLE,
            currency VARCHAR,
            source VARCHAR,
            fetched_at TIMESTAMP,
            PRIMARY KEY(ticker, ex_date)
        );

        -- Operational logging for data quality / ingestion gaps
        CREATE TABLE IF NOT EXISTS data_gaps (
            run_id VARCHAR,
            kind VARCHAR,         -- e.g., 'prices', 'news'
            ticker VARCHAR,
            start_date DATE,
            end_date DATE,
            requested_at TIMESTAMP,
            status VARCHAR,       -- 'SUCCESS' | 'FAILED' | 'SKIPPED'
            provider VARCHAR,
            message VARCHAR,
            rows_inserted INTEGER,
            rows_upserted INTEGER, -- inserted + updated (best-effort)
            error VARCHAR,
            duration_ms INTEGER,
            reason_code VARCHAR,          -- standardized classification of result
            requested_start_date DATE,    -- original requested start
            requested_end_date DATE,      -- original requested end
            obtained_start_date DATE,     -- min(date) actually obtained (after parsing)
            obtained_end_date DATE        -- max(date) actually obtained (after parsing)
        );

        -- Data Quality (PHASE1 DataOps)
        CREATE TABLE IF NOT EXISTS dq_runs (
            run_id VARCHAR PRIMARY KEY,
            kind VARCHAR,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            asof_date DATE,
            window_days INTEGER,
            status VARCHAR,
            notes VARCHAR,
            error VARCHAR
        );

        CREATE TABLE IF NOT EXISTS dq_findings (
            finding_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            kind VARCHAR,
            severity VARCHAR,
            market VARCHAR,
            ticker VARCHAR,
            start_date DATE,
            end_date DATE,
            count INTEGER,
            message VARCHAR,
            created_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS dq_metrics_daily (
            run_id VARCHAR,
            asof_date DATE,
            market VARCHAR,
            metric VARCHAR,
            value DOUBLE,
            created_at TIMESTAMPTZ,
            PRIMARY KEY(run_id, asof_date, market, metric)
        );

        -- Certification-grade run tracking
        CREATE TABLE IF NOT EXISTS audit_runs (
            run_id VARCHAR PRIMARY KEY,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            status VARCHAR,            -- 'SUCCESS' | 'FAILED' | 'RUNNING'
            universe_id VARCHAR,
            holding_period_sessions INTEGER,
            config_json VARCHAR,
            code_fingerprint VARCHAR,
            notes VARCHAR,
            error VARCHAR
        );

        CREATE TABLE IF NOT EXISTS audit_trades (
            trade_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            signal_date DATE,
            buy_date DATE,
            sell_date DATE,
            exit_reason VARCHAR,
            exit_is_fallback BOOLEAN,

            ticker VARCHAR,
            ticker_original VARCHAR,

            firm VARCHAR,
            rating VARCHAR,
            market VARCHAR,
            sector VARCHAR,
            instrument_type VARCHAR,

            mom_status VARCHAR,
            risk_vol DOUBLE,

            is_tobin_tax BOOLEAN,
            ftt_pct DOUBLE,

            sentiment_score DOUBLE,

            exec_shift_sessions INTEGER,
            exit_shift_sessions INTEGER,
            halt_reason VARCHAR,

            buy_price DOUBLE,
            sell_price DOUBLE,
            gross_return_pct DOUBLE,
            cost_pct DOUBLE,
            net_return_pct DOUBLE,
            trade_score DOUBLE,
            universe_id VARCHAR
        );

        CREATE TABLE IF NOT EXISTS audit_equity (
            run_id VARCHAR,
            date DATE,
            equity DOUBLE,
            cash DOUBLE,
            invested DOUBLE,
            positions INTEGER,
            tax_paid DOUBLE,
            executed_trades INTEGER,
            closed_trades INTEGER,
            PRIMARY KEY(run_id, date)
        );

        -- Signal store
        CREATE TABLE IF NOT EXISTS recs (
            date DATE,                 -- publication date (legacy-compatible)
            ticker VARCHAR,
            firm VARCHAR,
            rating VARCHAR,
            sentiment_score DOUBLE,
            headline VARCHAR,
            source_url VARCHAR,
            universe_id VARCHAR,
            published_at TIMESTAMP,
            PRIMARY KEY(date, ticker, firm)
        );

        CREATE TABLE IF NOT EXISTS momentum_rankings (
            date DATE,
            ticker VARCHAR,
            m_ret DOUBLE,
            rnk INTEGER,
            signal VARCHAR,
            PRIMARY KEY(date, ticker)
        );

        -- Dynamic universes and historical membership (survivorship-bias control)
        CREATE TABLE IF NOT EXISTS universes (
            universe_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            market VARCHAR,
            description VARCHAR
        );

        CREATE TABLE IF NOT EXISTS universe_membership (
            universe_id VARCHAR,
            ticker VARCHAR,
            start_date DATE,
            end_date DATE,
            source VARCHAR,
            notes VARCHAR,
            PRIMARY KEY(universe_id, ticker, start_date)
        );

        -- Time-bounded symbol mappings (corporate actions / ticker changes)
        CREATE TABLE IF NOT EXISTS ticker_mappings (
            alias_ticker VARCHAR,
            canonical_ticker VARCHAR,
            start_date DATE,
            end_date DATE,
            source VARCHAR,
            notes VARCHAR,
            PRIMARY KEY(alias_ticker, start_date)
        );

        -- Execution feasibility: ticker-level and market-level halts
        CREATE TABLE IF NOT EXISTS ticker_halts (
            ticker VARCHAR,
            start_date DATE,
            end_date DATE,
            reason VARCHAR,
            source VARCHAR,
            PRIMARY KEY(ticker, start_date)
        );

        CREATE TABLE IF NOT EXISTS market_halts (
            market VARCHAR,
            start_date DATE,
            end_date DATE,
            reason VARCHAR,
            source VARCHAR,
            PRIMARY KEY(market, start_date)
        );

        -- Local, deterministic sentiment cache
        CREATE TABLE IF NOT EXISTS sentiment_cache (
            text_hash VARCHAR PRIMARY KEY,
            text VARCHAR,
            score DOUBLE,
            model VARCHAR,
            computed_at TIMESTAMP
        );

        -- Optional decision ledger (includes skipped signals)
        CREATE TABLE IF NOT EXISTS audit_signal_decisions (
            decision_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            signal_date DATE,
            ticker_original VARCHAR,
            ticker VARCHAR,
            firm VARCHAR,
            rating VARCHAR,
            universe_id VARCHAR,

            intended_buy_date DATE,
            buy_date DATE,
            exec_shift_sessions INTEGER,

            intended_sell_date DATE,
            sell_date DATE,
            exit_shift_sessions INTEGER,

            decision VARCHAR,      -- 'EXECUTED' | 'SKIPPED' | 'DROPPED_DEDUP'
            skip_reason VARCHAR,
            halt_reason VARCHAR,

            created_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS execution_orders (
            order_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            created_at TIMESTAMPTZ,
            ticker VARCHAR,
            side VARCHAR,                -- 'BUY' | 'SELL'
            quantity DOUBLE,
            order_type VARCHAR,          -- e.g. 'MARKET' | 'LIMIT'
            limit_price DOUBLE,
            status VARCHAR,              -- e.g. 'NEW' | 'FILLED' | 'CANCELLED'
            notes VARCHAR
        );

        CREATE TABLE IF NOT EXISTS execution_fills (
            fill_id VARCHAR PRIMARY KEY,
            order_id VARCHAR,
            run_id VARCHAR,
            filled_at TIMESTAMPTZ,
            ticker VARCHAR,
            side VARCHAR,                -- 'BUY' | 'SELL'
            quantity DOUBLE,
            fill_price DOUBLE,
            fees DOUBLE,
            notes VARCHAR
        );
        """
    )

    # ---------------------------------------------------------------------
    # Backward-compatible columns (DBs created before the current schema)
    # ---------------------------------------------------------------------
    _add_column_if_missing(con, "prices", "open_price", "DOUBLE")
    _add_column_if_missing(con, "prices", "source", "VARCHAR")
    _add_column_if_missing(con, "prices", "fetched_at", "TIMESTAMP")

    # Ensure existing local datasets are explicitly labeled for audit provenance.
    # (We only fill NULLs; provider-sourced rows remain untouched.)
    try:
        con.execute("UPDATE prices SET source='legacy' WHERE source IS NULL")
    except Exception:
        pass

    for col, ddl in [
        ("sentiment_score", "DOUBLE"),
        ("headline", "VARCHAR"),
        ("source_url", "VARCHAR"),
        ("universe_id", "VARCHAR"),
        ("published_at", "TIMESTAMP"),
    ]:
        _add_column_if_missing(con, "recs", col, ddl)

    for col, ddl in [
        ("sector", "VARCHAR"),
        ("market", "VARCHAR"),
        ("currency", "VARCHAR"),
        ("instrument_type", "VARCHAR"),
        ("is_tobin_tax", "BOOLEAN DEFAULT FALSE"),
        ("ftt_rate", "DOUBLE"),
        ("yf_symbol", "VARCHAR"),
        ("stooq_symbol", "VARCHAR"),
    ]:
        _add_column_if_missing(con, "metadata", col, ddl)

    # audit_trades extensions (safe for older DBs)
    for col, ddl in [
        ("ticker_original", "VARCHAR"),
        ("instrument_type", "VARCHAR"),
        ("ftt_pct", "DOUBLE"),
        ("exec_shift_sessions", "INTEGER"),
        ("exit_shift_sessions", "INTEGER"),
        ("halt_reason", "VARCHAR"),
    ]:
        _add_column_if_missing(con, "audit_trades", col, ddl)

    # data_gaps extensions
    for col, ddl in [
        ("run_id", "VARCHAR"),
        ("status", "VARCHAR"),
        ("provider", "VARCHAR"),
        ("message", "VARCHAR"),
        ("rows_inserted", "INTEGER"),
        ("rows_upserted", "INTEGER"),
        ("error", "VARCHAR"),
        ("duration_ms", "INTEGER"),
        ("reason_code", "VARCHAR"),
        ("requested_start_date", "DATE"),
        ("requested_end_date", "DATE"),
        ("obtained_start_date", "DATE"),
        ("obtained_end_date", "DATE"),
    ]:
        _add_column_if_missing(con, "data_gaps", col, ddl)


def seed_default_universes(con: duckdb.DuckDBPyConnection) -> None:
    """Seed universes and membership for the tickers present in the local DB.

    IMPORTANT
    ---------
    This does NOT ship historical index membership. It only registers what you
    already have locally, so that analytics can be filtered by `universe_id`.
    """

    ensure_schema(con)

    seeds = [
        UniverseSeed("ALL", "All available tickers", "MULTI", "Union of all tickers present in the local DB"),
        UniverseSeed("US", "US universe (local)", "US", "Tickers inferred as US from metadata/format"),
        UniverseSeed("EU", "EU universe (local)", "EU", "Tickers inferred as EU from metadata/format"),
    ]

    for s in seeds:
        con.execute(
            """
            INSERT INTO universes(universe_id, name, market, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(universe_id) DO UPDATE SET
              name=excluded.name,
              market=excluded.market,
              description=excluded.description
            """,
            [s.universe_id, s.name, s.market, s.description],
        )

    # Determine tickers from the DB itself (preferred): metadata -> prices -> recs
    tickers: list[str] = []
    if _table_exists(con, "metadata"):
        tickers = [r[0] for r in con.execute("SELECT ticker FROM metadata ORDER BY ticker").fetchall()]

    if not tickers and _table_exists(con, "prices"):
        tickers = [r[0] for r in con.execute("SELECT DISTINCT ticker FROM prices ORDER BY ticker").fetchall()]

    if not tickers and _table_exists(con, "recs"):
        tickers = [r[0] for r in con.execute("SELECT DISTINCT ticker FROM recs ORDER BY ticker").fetchall()]

    if not tickers:
        return

    def is_eu(t: str) -> bool:
        return "." in t  # e.g., ASML.AS, SAP.DE

    # If metadata exists, enforce a non-null, deterministic market label.
    if _table_exists(con, "metadata"):
        con.execute(
            """
            UPDATE metadata
            SET market = CASE WHEN ticker LIKE '%.%' THEN 'EU' ELSE 'US' END
            WHERE market IS NULL OR TRIM(COALESCE(market, '')) = ''
            """
        )

    min_date = None
    if _table_exists(con, "prices"):
        min_date = con.execute("SELECT MIN(date) FROM prices").fetchone()[0]

    start_date = min_date

    # If we don't have prices yet, still seed membership with an open-ended interval.
    for t in tickers:
        con.execute(
            """
            INSERT INTO universe_membership(universe_id, ticker, start_date, end_date, source, notes)
            VALUES ('ALL', ?, ?, NULL, 'seed_default', 'seeded from local DB')
            ON CONFLICT(universe_id, ticker, start_date) DO NOTHING
            """,
            [t, start_date],
        )

        uid = "EU" if is_eu(t) else "US"
        con.execute(
            """
            INSERT INTO universe_membership(universe_id, ticker, start_date, end_date, source, notes)
            VALUES (?, ?, ?, NULL, 'seed_default', 'seeded from local DB')
            ON CONFLICT(universe_id, ticker, start_date) DO NOTHING
            """,
            [uid, t, start_date],
        )


def list_universes(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    ensure_schema(con)
    rows = con.execute("SELECT universe_id, name FROM universes ORDER BY universe_id").fetchall()
    return [(r[0], r[1]) for r in rows]


def cli_migrate(db_path: str) -> None:
    con = duckdb.connect(db_path)
    try:
        ensure_schema(con)
        seed_default_universes(con)
    finally:
        con.close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="SENTINEL-ALPHA DuckDB schema migration")
    p.add_argument("--db", default="data/sentinel_alpha.db", help="Path to DuckDB database file")
    args = p.parse_args()

    cli_migrate(args.db)
    print(f"[+] Migration completed: {args.db}")
