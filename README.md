# BookScouter

A local desktop tool for entering a book ISBN and seeing prices across
several online shops at a glance. Every lookup is stored locally, so price
history for a title can be tracked over time.

> **Status:** Works end-to-end against 14 live shops, through the graphical
> interface, the command line, and a standalone Windows `.exe`.

## Why this project

Book prices vary noticeably between shops and change over time. Checking four
or five shops by hand for every purchase is tedious, and it is easy to forget
what a title cost last month. BookScouter automates the comparison and keeps
a local record of what each title has cost.

## Supported shops

- thalia.at
- thalia.de
- buecher.de
- osiander.de
- orellfuessli.ch — quotes Swiss francs; see [Currencies](#currencies)
- morawa.at
- waltscomicshop.com
- danibooks.de — comic and manga publisher selling direct
- altraverse.de — manga publisher selling direct; only carries
  German-language ISBNs (`978-3-…`), so other ISBNs are skipped without a
  request
- lehmanns.de — general bookseller; reached through a search path its
  robots.txt disallows, because the product URL contains an internal article
  number and is not derivable from the ISBN (see
  `bookscouter/scrapers/lehmanns.py`)
- buch7.de — general bookseller donating most of its profit
- blackwells.co.uk — British bookseller with a large English-language manga
  and light novel range; prices depend on your location, see
  [Currencies](#currencies)
- wordery.com — British bookseller, likewise English-language; quotes pounds
- amazon.de — verified against the live site, but Amazon's terms explicitly
  prohibit automated access (unlike the others, which only have a
  robots.txt courtesy exception, see `bookscouter/scrapers/amazon.py`); weigh
  that before enabling it

Every shop implements the same `Scraper` interface (ISBN in, title + price
out), so adding another one means writing a single class. Five of them —
thalia.at, thalia.de, buecher.de, osiander.de and orellfuessli.ch — run on
the same shop platform and share one scraper, so each is only a subclass
naming its own domain.

### A note on German fixed book prices

German law binds the retail price of German-published books, so thalia.de,
buecher.de, osiander.de, lehmanns.de and buch7.de will all quote the same
figure for, say, a Carlsen manga. That is not a bug in the comparison — it is
the law, and seeing it confirmed is itself useful. Where these shops do
differ is availability and delivery time, and neither imported nor
English-language editions are price-bound. Blackwell's and Wordery are the
two shops where manga prices genuinely move: for the same volume they can sit
several euros apart, and apart from both from the German retailers.

## Currencies

Every price is stored and compared in euros, so one column and one chart axis
mean the same thing everywhere. Three shops sit outside the euro area: Orell
Füssli quotes Swiss francs, Wordery quotes pounds, and Blackwell's quotes
whichever currency it picks for your location — euros from inside the euro
area, pounds otherwise. All of them are converted using the European Central
Bank's daily reference rates, fetched at most once a day and cached in your
user profile so the app still works offline.

Converted rows always show the shop's own price too — `31.79 EUR (umgerechnet
aus 29.90 CHF)` — because the foreign amount is the actual shelf price. Bear
in mind that stored history keeps the euro value from the day of the lookup,
so an old Orell Füssli entry reflects that day's exchange rate as well as
that day's price. If no rate can be fetched and none was ever cached, that
shop reports no result rather than passing a franc or pound amount off as
euros.

## Requirements

- Python 3.12+
- `curl` on the system path (see [How it works](#how-it-works))

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

## Usage

### Windows: BookScouter.exe

Double-click `BookScouter.exe` in the project folder. No Python installation
and no setup needed — it is a single self-contained file.

The `.exe` is not checked into the repository (it is 14 MB of build output).
Build it with:

```bash
pyinstaller BookScouter.spec --distpath . --workpath build --noconfirm
```

The app icon is not a checked-in binary either: `assets/make_icon.py` draws it
and writes `assets/BookScouter.ico`, using nothing but the standard library.
Run it after changing the design.

### Graphical interface

```bash
python -m bookscouter.ui
```

Enter an ISBN (hyphens and spaces are fine) and press Enter or click
**Suchen**. Shops are queried one after another and each result appears as
soon as that shop answers, so the window stays responsive throughout the
roughly half a minute a full lookup across all 14 shops takes.

A checkbox per shop sits under the input field. All of them start ticked;
unticking one leaves it out of the next lookup, which is the quickest way to
cut the waiting time when only one or two shops interest you. The selection
applies to the current session and is not saved between starts. The price
history chart keeps showing every shop it has data for, so a shop's line
keeps its colour whether or not it was queried this time.

Each row shows the shop's price, how it changed since the last lookup (red if
the book got more expensive, green if it got cheaper), whether the shop has
it in stock, and a link straight to that shop's product page. Underneath, a
chart plots the price history per shop; hovering it snaps to a day and lists
what every shop charged that day.

Shops that report no stock information are shown as "Unbekannt" rather than
being guessed at.

### Command line

```bash
python -m bookscouter.main 9783546100335
```

```
Die Straße - Thalia.at: 26.50 EUR – Auf Lager
  https://www.thalia.at/shop/home/artikeldetails/A1077153279
Die Straße - Thalia.de: 25.00 EUR – Auf Lager
  https://www.thalia.de/shop/home/artikeldetails/A1077153279
Die Straße - Morawa.at: 26.95 EUR – Auf Lager
  https://www.morawa.at/detail/ISBN-9783546100335
Nicht gefunden bei Walt's Comic Shop.
Die Straße - Osiander.de: 25.00 EUR – Auf Lager
  https://www.osiander.de/shop/home/artikeldetails/A1077153279
Die Straße - Orell Füssli: 39.23 EUR (umgerechnet aus 36.90 CHF) – Auf Lager
  https://www.orellfuessli.ch/shop/home/artikeldetails/A1077153279
Nicht gefunden bei altraverse.
```

Look the same ISBN up again later and previous prices are listed alongside
the current ones:

```
Bisherige Preise:
  2026-07-25T19:32:07.862179+00:00: 26.50 EUR (Thalia.at)
  2026-07-25T19:32:10.831537+00:00: 25.00 EUR (Thalia.de)
```

Shops that do not carry the title are reported individually; the command
exits with a non-zero status only if no shop had the book at all.

Results are written to a local SQLite file in your user profile
(`%LOCALAPPDATA%\BookScouter\bookscouter.db` on Windows), so the price history
is the same no matter which directory the app is started from. ISBN-10 input
is converted to the equivalent ISBN-13 before storing, so looking a book up
either way keeps a single history.

## Running the tests

```bash
python -m pytest
```

The scraper tests use recorded HTML/JSON fixtures and make no network
requests.

## How it works

Each scraper subclasses `Scraper` (`bookscouter/scrapers/base.py`) and
implements `scrape(isbn) -> ScrapeResult`. The base class wraps the shared
HTTP helper (`bookscouter/http.py`) with a minimum delay between requests.
All scrapers are registered once in `bookscouter/scrapers/__init__.py`, so
the interface and the command line both pick up a new shop automatically.

The interface runs the lookup on a background thread and hands results back
to the Tk main loop through a `queue.Queue`, which the main loop drains on a
timer. That keeps the window responsive while requests are in flight and
lets each shop's row appear the moment it arrives. All database access
happens on the worker thread using its own connection, since SQLite
connections must not be shared across threads.

That helper shells out to `curl` rather than using Python's `requests`
library: several of these shops sit behind bot protection that blocks the TLS
fingerprint of Python HTTP clients outright, returning 403 regardless of
headers. `curl` gets through while still sending the project's own honest
User-Agent, which keeps the tool identifiable rather than pretending to be a
browser.

Prices, titles and stock status are read from each page's structured data
(JSON-LD, Microdata, or Shopify's product JSON) instead of scraped out of
layout markup, which is considerably more stable across site redesigns.
Stock comes from the `availability` field of the offer, mapped from
schema.org's vocabulary onto a handful of German labels; a shop that omits
it reports "Unbekannt", so a missing field is never mistaken for "out of
stock".

## Usage & legal notes

- The tool runs entirely locally on the user's own machine — no central
  server, no hosting, no shared database.
- Lookups happen per ISBN on request. There is no bulk crawling of catalogues,
  and a rate limit applies between requests.
- The scrapers send an honest User-Agent identifying the tool; they do not
  impersonate a browser.
- No scraped data is committed to this repository — code only.
- Users are responsible for complying with the terms of service of whichever
  shops they configure.

## License

[MIT](LICENSE)
