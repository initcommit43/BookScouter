"""Tests für das Zerlegen der curl-Ausgabe in `bookscouter.http`.

Interessant ist hier nur eines: curl hängt Statuscode und schliesslich
erreichte URL als zwei zusätzliche Zeilen an den Body an, und der Body
selbst besteht aus lauter Zeilen. Wer von vorn zerlegt, zerschneidet die
Antwort.
"""

from dataclasses import dataclass

from bookscouter import http


@dataclass
class FakeCompletedProcess:
    stdout: str


def _curl_antwortet(monkeypatch, stdout):
    monkeypatch.setattr(
        http.subprocess, "run", lambda *args, **kwargs: FakeCompletedProcess(stdout)
    )


def test_body_status_und_url(monkeypatch):
    _curl_antwortet(monkeypatch, "<html>Hallo</html>\n200\nhttps://example.org/buch")

    antwort = http.hole("https://example.org/suche")

    assert antwort.text == "<html>Hallo</html>"
    assert antwort.ok is True
    assert antwort.status_code == 200
    assert antwort.url == "https://example.org/buch"


def test_body_mit_zeilenumbruechen_bleibt_heil(monkeypatch):
    """Der Regelfall: HTML über viele Zeilen, gefolgt von den zwei Zusatzzeilen."""
    body = "<html>\n  <body>\n    <h1>Titel</h1>\n  </body>\n</html>"
    _curl_antwortet(monkeypatch, f"{body}\n200\nhttps://example.org/buch")

    antwort = http.hole("https://example.org/suche")

    assert antwort.text == body
    assert antwort.url == "https://example.org/buch"


def test_umleitung_liefert_zieladresse(monkeypatch):
    """Genau dafür gibt es das Feld: Lehmanns, buch7 und Wordery leiten um."""
    _curl_antwortet(
        monkeypatch,
        "<html></html>\n200\nhttps://www.buch7.de/produkt/x/1?ean=9783551741035",
    )

    antwort = http.hole("https://www.buch7.de/suche", params={"search": "9783551741035"})

    assert antwort.url == "https://www.buch7.de/produkt/x/1?ean=9783551741035"


def test_fehlerstatus_ist_nicht_ok(monkeypatch):
    _curl_antwortet(monkeypatch, "Not Found\n404\nhttps://example.org/weg")

    antwort = http.hole("https://example.org/weg")

    assert antwort.ok is False
    assert antwort.status_code == 404


def test_verbindungsfehler_behaelt_angefragte_url(monkeypatch):
    """Ohne Netz schreibt curl nichts – dann ist die angefragte URL die bessere Auskunft."""
    _curl_antwortet(monkeypatch, "")

    antwort = http.hole("https://example.org/suche", params={"q": "1"})

    assert antwort.ok is False
    assert antwort.status_code == 0
    assert antwort.url == "https://example.org/suche?q=1"
