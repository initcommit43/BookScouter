"""SQLite-Anbindung für BookScouter.

Schema (Tabelle `price_lookups`): id, isbn, titel, shop, preis, datum.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bookscouter.config import DB_PATH
from bookscouter.isbn import to_isbn13

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_lookups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT NOT NULL,
    titel TEXT NOT NULL,
    shop TEXT NOT NULL,
    preis REAL NOT NULL,
    datum TEXT NOT NULL
);
"""


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    _isbn10_zeilen_umschreiben(conn)
    return conn


def _isbn10_zeilen_umschreiben(conn: sqlite3.Connection) -> None:
    """Schreibt Altbestände mit ISBN-10 auf die gleichwertige ISBN-13 um.

    Früher wurde die ISBN so gespeichert, wie sie eingetippt wurde – dasselbe
    Buch als ISBN-10 und als ISBN-13 gesucht ergab damit zwei getrennte
    Preisverläufe (und zwei Linien im Chart). CLI und UI speichern inzwischen
    nur noch ISBN-13; hier werden die vorhandenen Zeilen nachgezogen.
    """
    alte = [
        zeile[0]
        for zeile in conn.execute(
            "SELECT DISTINCT isbn FROM price_lookups WHERE length(isbn) = 10"
        )
    ]
    for alt in alte:
        neu = to_isbn13(alt)
        if neu != alt:
            conn.execute("UPDATE price_lookups SET isbn = ? WHERE isbn = ?", (neu, alt))
    if alte:
        conn.commit()


def save_lookup(
    conn: sqlite3.Connection, isbn: str, titel: str, shop: str, preis: float
) -> None:
    conn.execute(
        "INSERT INTO price_lookups (isbn, titel, shop, preis, datum) VALUES (?, ?, ?, ?, ?)",
        (isbn, titel, shop, preis, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_price_history(conn: sqlite3.Connection, isbn: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT isbn, titel, shop, preis, datum FROM price_lookups"
        " WHERE isbn = ? ORDER BY datum ASC",
        (isbn,),
    )
    return cursor.fetchall()
