"""Der eine HTTP-Aufruf des Projekts, den sich alle Abrufer teilen.

Eigenes Modul und nicht Teil von `scrapers/base.py`, weil ausser den Shop-
Scrapern auch der Wechselkurs-Abruf in `bookscouter/waehrung.py` genau diese
curl-Flags braucht. Läge die Funktion bei den Scrapern, müsste `waehrung`
von `scrapers` abhängen und `scrapers.thalia` zugleich von `waehrung` – ein
Importzirkel. Hier hängt nichts an etwas anderem als der Konfiguration.
"""

import subprocess
from dataclasses import dataclass
from urllib.parse import urlencode

from bookscouter.config import USER_AGENT

# Ohne dieses Flag blitzt unter Windows bei jedem curl-Aufruf kurz ein
# Konsolenfenster auf – in der gepackten .exe, die selbst keine Konsole hat,
# wären das pro Suche bis zu zehn Blitzer. Nur unter Windows vorhanden.
_OHNE_KONSOLENFENSTER = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class HttpResponse:
    text: str
    ok: bool
    status_code: int
    # Die URL, bei der curl nach allen Weiterleitungen gelandet ist. Mehrere
    # Shops (Lehmanns, buch7, Wordery) beantworten eine ISBN-Suche mit einer
    # Weiterleitung auf die Produktseite; deren Adresse ist erst danach
    # bekannt, wird aber als Link im Ergebnis gebraucht. Mit Vorgabewert,
    # damit Aufrufer, die sie nicht brauchen, unverändert bleiben.
    url: str = ""


def hole(url: str, params: dict | None = None) -> HttpResponse:
    """Ein einzelner GET-Request – ohne Rate-Limiting, das macht `Scraper._get`.

    Nutzt den `curl`-Befehl statt der `requests`-Bibliothek: manche Shops
    (z. B. Thalia) blocken den TLS-Fingerabdruck von Python-HTTP-Clients
    per Cloudflare, unabhängig vom User-Agent-Header. curl mit demselben
    ehrlichen User-Agent kommt durch, ohne einen Browser vorzutäuschen.

    Das `-w`-Format hängt zwei Zeilen an den Body an: Statuscode und
    schliesslich erreichte URL. Beide werden von hinten abgeschnitten, denn
    der Body selbst enthält reichlich Zeilenumbrüche.

    `--compressed` ist Pflicht: amazon.de liefert manche Antworten
    unangefragt gzip-komprimiert. Ohne das Flag landen die rohen
    gzip-Bytes in `text=True`/`encoding="utf-8"` und werden lautlos zu
    Ersatzzeichen – live beobachtet, dabei sah eine echte "auf Lager"-
    Antwort wie "nicht gefunden" aus. Für Shops ohne Kompression ändert
    das Flag nichts.
    """
    if params:
        url = f"{url}?{urlencode(params)}"

    result = subprocess.run(
        [
            "curl", "-s", "-L", "--compressed", "--max-time", "10",
            "-A", USER_AGENT, "-w", "\n%{http_code}\n%{url_effective}", url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_OHNE_KONSOLENFENSTER,
    )

    ohne_url, _, effektive_url = result.stdout.rpartition("\n")
    body, _, status_text = ohne_url.rpartition("\n")
    status_code = int(status_text) if status_text.isdigit() else 0
    return HttpResponse(
        text=body,
        ok=200 <= status_code < 300,
        status_code=status_code,
        # Bei einem Verbindungsfehler schreibt curl nichts auf die Standard-
        # ausgabe; dann bleibt die angefragte URL stehen statt einer leeren
        # Zeichenkette – für den Aufrufer die brauchbarere Auskunft.
        url=effektive_url.strip() or url,
    )
