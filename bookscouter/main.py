"""Kommandozeilen-Variante der Suche.

Nimmt eine oder mehrere ISBNs entgegen und fragt für jede alle Shops ab.
Die grafische Oberfläche liegt in `bookscouter/ui.py` und wird mit
`python -m bookscouter.ui` gestartet; beide teilen sich Scraper-Liste,
ISBN-Normalisierung und Datenbank.
"""

import sys

from bookscouter.db import connect, get_price_history, save_lookup
from bookscouter.isbn import parse_isbn_liste
from bookscouter.scrapers import ALL_SCRAPERS


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("Verwendung: python -m bookscouter.main <ISBN> [<ISBN> …]")
        sys.exit(1)

    # ISBN-13 ist der einheitliche Schlüssel: sonst bekäme dasselbe Buch je
    # nach eingetippter Schreibweise zwei getrennte Preisverläufe.
    isbns = parse_isbn_liste(" ; ".join(sys.argv[1:]))
    if not isbns:
        print("Keine ISBN erkannt.")
        sys.exit(1)

    conn = connect()
    # Die Scraper einmal anlegen und über alle Bücher hinweg weiterverwenden:
    # der Mindestabstand zwischen zwei Anfragen an denselben Shop hängt am
    # einzelnen Scraper-Objekt (`Scraper._get`). Pro Buch neue Objekte würden
    # ihn jedes Mal vergessen.
    scraper = [scraper_cls() for scraper_cls in ALL_SCRAPERS]
    irgendwo_gefunden = False

    for isbn in isbns:
        if len(isbns) > 1:
            print(f"\n=== {isbn} ===")
        if _frage_buch_ab(conn, scraper, isbn):
            irgendwo_gefunden = True

    conn.close()
    if not irgendwo_gefunden:
        sys.exit(1)


def _frage_buch_ab(conn, scraper: list, isbn: str) -> bool:
    """Fragt alle Shops zu einer ISBN ab. Rückgabe: irgendwo gefunden?"""
    history = get_price_history(conn, isbn)
    gefunden = False

    for shop in scraper:
        result = shop.scrape(isbn)
        if not result.gefunden:
            print(f"Nicht gefunden bei {shop.shop_name}.")
            continue

        gefunden = True
        preis_text = f"{result.preis:.2f} EUR"
        if result.originalwaehrung:
            # Nicht verschweigen, dass hier ein Wechselkurs im Spiel war –
            # der Ladenpreis ist der Betrag in Klammern, nicht der Euro-Wert.
            preis_text += (
                f" (umgerechnet aus {result.originalpreis:.2f} {result.originalwaehrung})"
            )
        print(f"{result.titel} - {result.shop}: {preis_text} – {result.verfuegbarkeit}")
        if result.url:
            print(f"  {result.url}")
        save_lookup(conn, isbn=isbn, titel=result.titel, shop=result.shop, preis=result.preis)

    if history:
        print("Bisherige Preise:")
        for row in history:
            print(f"  {row['datum']}: {row['preis']:.2f} EUR ({row['shop']})")

    return gefunden


if __name__ == "__main__":
    main()
