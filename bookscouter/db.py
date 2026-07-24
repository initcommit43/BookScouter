"""SQLite-Anbindung für BookScouter.

Schema (Tabelle `price_lookups`): id, isbn, titel, shop, preis, datum.
"""

import sqlite3
from datetime import datetime, timezone

from bookscouter.config import DB_PATH

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
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


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
