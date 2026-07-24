"""Einstiegspunkt. UI-Start folgt in Phase 3, Phase 1 nutzt dies als CLI-Test."""

import sys

from bookscouter.db import connect, get_price_history, save_lookup
from bookscouter.scrapers.thalia import ThaliaScraper


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) != 2:
        print("Verwendung: python -m bookscouter.main <ISBN>")
        sys.exit(1)

    isbn = sys.argv[1]
    scraper = ThaliaScraper()
    result = scraper.scrape(isbn)

    if not result.gefunden:
        print(f"Nicht gefunden bei {scraper.shop_name} für ISBN {isbn}.")
        sys.exit(1)

    conn = connect()
    history = get_price_history(conn, isbn)
    print(f"{result.titel} - {result.shop}: {result.preis:.2f} EUR")
    if history:
        print("Bisherige Preise:")
        for row in history:
            print(f"  {row['datum']}: {row['preis']:.2f} EUR ({row['shop']})")

    save_lookup(conn, isbn=isbn, titel=result.titel, shop=result.shop, preis=result.preis)
    conn.close()


if __name__ == "__main__":
    main()
