# BookScouter

A local desktop tool for entering a book ISBN and seeing prices across
several online shops at a glance. Every lookup is stored locally, so price
history for a title can be tracked over time.

> **Status:** Core logic and command-line interface work end-to-end against
> five live shops. The graphical interface (customtkinter) is not built yet —
> see [Roadmap](#roadmap).

## Why this project

Book prices vary noticeably between shops and change over time. Checking four
or five shops by hand for every purchase is tedious, and it is easy to forget
what a title cost last month. BookScouter automates the comparison and keeps
a local record of what each title has cost.

## Supported shops

| Shop | Platform | Lookup |
|---|---|---|
| thalia.at | Thalia | search → detail page, JSON-LD |
| thalia.de | Thalia | search → detail page, JSON-LD |
| buecher.de | Thalia | search → detail page, JSON-LD |
| morawa.at | Morawa | direct ISBN URL, JSON-LD |
| waltscomicshop.com | Shopify | search → product JSON endpoint |

Every shop implements the same `Scraper` interface (ISBN in, title + price
out), so adding another one means writing a single class.

Two details worth noting, since they shaped the code:

- **buecher.de runs on the Thalia platform** — same URL structure, same
  article IDs, same markup. All three Thalia-platform shops are therefore
  handled by one parametrised scraper rather than three near-copies. Their
  prices do differ, so they remain separate entries.
- **morawa.at exposes a direct, ISBN-addressable product URL**
  (`/detail/ISBN-<isbn>`), so it needs a single request instead of a search
  step followed by a detail request.

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
HTTP helper, which enforces a minimum delay between requests.

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

## Roadmap

- [x] Core lookup logic, SQLite storage, price history
- [x] Multiple shops behind a shared interface
- [ ] customtkinter interface (search field, result table, price history)
- [ ] Packaging as a single `.exe` via PyInstaller
- [ ] Optional: price-history chart, CSV export

## License

[MIT](LICENSE)
