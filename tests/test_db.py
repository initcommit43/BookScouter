from bookscouter.db import connect


def test_connect_creates_schema(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(str(db_path))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='price_lookups'"
    ).fetchall()
    assert len(tables) == 1
