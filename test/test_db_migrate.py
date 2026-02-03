import duckdb

from src.phase0.db.migrate import ensure_schema, seed_default_universes


def test_schema_and_seed_idempotent():
    con = duckdb.connect(database=':memory:')
    ensure_schema(con)
    seed_default_universes(con)
    # Running twice should not crash
    ensure_schema(con)
    seed_default_universes(con)

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert 'prices' in tables
    assert 'recs' in tables
    assert 'universes' in tables
    assert 'universe_membership' in tables

    # Universes seeded
    u = con.execute("SELECT COUNT(*) FROM universes").fetchone()[0]
    assert u >= 1


def test_execution_tables_and_insert_idempotent():
    con = duckdb.connect(database=':memory:')
    ensure_schema(con)

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert 'execution_orders' in tables
    assert 'execution_fills' in tables

    con.execute(
        """
        INSERT INTO execution_orders(
            order_id, run_id, created_at, ticker, side, quantity,
            order_type, limit_price, status, notes
        )
        VALUES ('O1', 'R1', now(), 'AAPL', 'BUY', 1.0, 'MARKET', NULL, 'NEW', NULL)
        ON CONFLICT(order_id) DO NOTHING
        """
    )
    con.execute(
        """
        INSERT INTO execution_fills(
            fill_id, order_id, run_id, filled_at, ticker, side,
            quantity, fill_price, fees, notes
        )
        VALUES ('F1', 'O1', 'R1', now(), 'AAPL', 'BUY', 1.0, 100.0, 0.1, NULL)
        ON CONFLICT(fill_id) DO NOTHING
        """
    )

    ensure_schema(con)
    con.execute(
        """
        INSERT INTO execution_orders(
            order_id, run_id, created_at, ticker, side, quantity,
            order_type, limit_price, status, notes
        )
        VALUES ('O1', 'R1', now(), 'AAPL', 'BUY', 1.0, 'MARKET', NULL, 'NEW', NULL)
        ON CONFLICT(order_id) DO NOTHING
        """
    )
    con.execute(
        """
        INSERT INTO execution_fills(
            fill_id, order_id, run_id, filled_at, ticker, side,
            quantity, fill_price, fees, notes
        )
        VALUES ('F1', 'O1', 'R1', now(), 'AAPL', 'BUY', 1.0, 100.0, 0.1, NULL)
        ON CONFLICT(fill_id) DO NOTHING
        """
    )

    assert con.execute("SELECT COUNT(*) FROM execution_orders").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM execution_fills").fetchone()[0] == 1
