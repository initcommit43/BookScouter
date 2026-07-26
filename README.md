# BookScouter

A local desktop tool for entering a book ISBN and seeing prices across
several online shops at a glance. Every lookup is stored locally, so price
history for a title can be tracked over time.

> **Status:** Works end-to-end against five live shops, through both the
> graphical interface and the command line. Packaging as a standalone `.exe`
> is still open.

## Why this project

Book prices vary noticeably between shops and change over time. Checking four
or five shops by hand for every purchase is tedious, and it is easy to forget
what a title cost last month. BookScouter automates the comparison and keeps
a local record of what each title has cost.

## Supported shops

- thalia.at
- thalia.de
- buecher.de
- morawa.at
- waltscomicshop.com

Every shop implements the same `Scraper` interface (ISBN in, title + price
out), so adding another one means writing a single class.

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

### Graphical interface

```bash
python -m bookscouter.ui
```

Enter an ISBN (hyphens and spaces are fine) and press Enter or click
**Suchen**. Shops are queried one after another and each result appears as
soon as that shop answers, so the window stays responsive throughout the
roughly ten seconds a full lookup takes.

Each row shows the current price next to the last price recorded for that
shop, with the difference colour-coded — red if the book got more expensive,
green if it got cheaper. A collapsible panel underneath lists earlier
lookups for the same ISBN.

### Command line

```bash
python -m bookscouter.main 9783546100335
```

```
Die Straße - Thalia.at: 26.50 EUR
Die Straße - Thalia.de: 25.00 EUR
Die Straße - Buecher.de: 25.00 EUR
Die Straße - Morawa.at: 26.95 EUR
Nicht gefunden bei Walt's Comic Shop.
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

Results are written to a local SQLite file (`bookscouter.db`, gitignored).

## Running the tests

```bash
python -m pytest
```

The scraper tests use recorded HTML/JSON fixtures and make no network
requests.

## How it works

Each scraper subclasses `Scraper` (`bookscouter/scrapers/base.py`) and
implements `scrape(isbn) -> ScrapeResult`. The base class provides the shared
HTTP helper, which enforces a minimum delay between requests. All scrapers
are registered once in `bookscouter/scrapers/__init__.py`, so the interface
and the command line both pick up a new shop automatically.

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

Prices and titles are read from each page's structured data (JSON-LD, or
Shopify's product JSON) instead of scraped out of layout markup, which is
considerably more stable across site redesigns.

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
