"""Kommandozeilen-Variante der Suche.

Die grafische Oberfläche liegt in `bookscouter/ui.py` und wird mit
`python -m bookscouter.ui` gestartet; beide teilen sich Scraper-Liste,
ISBN-Normalisierung und Datenbank.
"""

import sys

from bookscouter.db import connect, get_price_history, save_lookup
from bookscouter.isbn import to_isbn13
from bookscouter.scrapers import ALL_SCRAPERS


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) != 2:
        print("Verwendung: python -m bookscouter.main <ISBN>")
        sys.exit(1)

    # ISBN-13 ist der einheitliche Schlüssel: sonst bekäme dasselbe Buch je
    # nach eingetippter Schreibweise zwei getrennte Preisverläufe.
    isbn = to_isbn13(sys.argv[1])
    conn = connect()
    history = get_price_history(conn, isbn)
    gefunden = False

    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        result = scraper.scrape(isbn)
        if not result.gefunden:
            print(f"Nicht gefunden bei {scraper.shop_name}.")
            continue

        gefunden = True
        print(f"{result.titel} - {result.shop}: {result.preis:.2f} EUR – {result.verfuegbarkeit}")
        if result.url:
            print(f"  {result.url}")
        save_lookup(conn, isbn=isbn, titel=result.titel, shop=result.shop, preis=result.preis)

    if history:
        print("Bisherige Preise:")
        for row in history:
            print(f"  {row['datum']}: {row['preis']:.2f} EUR ({row['shop']})")

    conn.close()
    if not gefunden:
        sys.exit(1)


if __name__ == "__main__":
    main()
