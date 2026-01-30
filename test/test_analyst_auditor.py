import duckdb

from src.db.migrate import ensure_schema, seed_default_universes


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
