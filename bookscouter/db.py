"""SQLite-Anbindung für BookScouter.

Schema (Tabelle `price_lookups`): id, isbn, titel, shop, preis, datum.
Wird in Phase 1 implementiert.
"""

import sqlite3

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
