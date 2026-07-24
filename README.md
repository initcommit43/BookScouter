# BookScouter

A local desktop tool for entering a book title or ISBN and seeing prices
across several selected online shops at a glance. Every lookup is stored
locally, so price history over time can be tracked.

> **Status:** In development — currently just a project scaffold.

## Why this project

Book prices can vary noticeably between shops and change over time.
BookScouter automates the manual comparison and keeps track of what a title
has cost over time.

## Tech stack

- **Python** — the only language used across the project
- **curl (via subprocess) + BeautifulSoup** — scraping (curl avoids TLS-fingerprint blocks some shops apply to Python HTTP clients)
- **sqlite3** (standard library) — local storage, a single file
- **customtkinter** — UI, pure Python without a server/browser
- **PyInstaller** — distributed as a single `.exe`

## Usage & legal notes

- The tool runs entirely locally on the user's own machine — no central
  server, no hosting.
- Lookups happen per ISBN/title on request, no systematic bulk crawling.
- No scraped data is committed to this repository — code only.
- Users are responsible for complying with the terms of service of whichever
  shops they configure.

## Setup (coming soon)

Will be added once the core logic (Phase 1) is in place.

## License

[MIT](LICENSE)
