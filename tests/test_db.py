from bookscouter.db import connect, get_price_history, save_lookup


def test_connect_creates_schema(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(str(db_path))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='price_lookups'"
    ).fetchall()
    assert len(tables) == 1


def test_connect_creates_missing_directory(tmp_path):
    # Beim ersten Start liegt der Ordner im Benutzerprofil noch nicht vor.
    db_path = tmp_path / "neu" / "unterordner" / "test.db"
    connect(str(db_path))
    assert db_path.exists()


def test_connect_rewrites_isbn10_rows_to_isbn13(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = connect(db_path)
    save_lookup(conn, isbn="3831041652", titel="Alt", shop="Thalia.at", preis=13.90)
    save_lookup(conn, isbn="9783831041657", titel="Neu", shop="Thalia.at", preis=12.95)
    conn.close()

    # Die Migration läuft beim nächsten Verbindungsaufbau.
    conn = connect(db_path)
    historie = get_price_history(conn, "9783831041657")
    assert [zeile["titel"] for zeile in historie] == ["Alt", "Neu"]
    assert get_price_history(conn, "3831041652") == []


def test_connect_leaves_unconvertible_isbn10_rows_alone(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = connect(db_path)
    save_lookup(conn, isbn="KEINEISBN", titel="Krumm", shop="Thalia.at", preis=1.00)
    conn.close()

    conn = connect(db_path)
    assert len(get_price_history(conn, "KEINEISBN")) == 1
