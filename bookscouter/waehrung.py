"""Umrechnung fremder Währungen in Euro, für Shops ausserhalb der Eurozone.

Bisher betrifft das allein Orell Füssli, das in Schweizer Franken auszeichnet.
Ohne Umrechnung stünde in derselben Ergebnisliste, im selben Chart und in
derselben Datenbankspalte einmal ein Euro- und einmal ein Franken-Betrag –
der Preisvergleich, um den es in diesem Tool geht, wäre damit hinfällig.

Kursquelle sind die Referenzkurse der Europäischen Zentralbank. Sie brauchen
keinen API-Schlüssel (in einer ausgelieferten .exe wäre einer ohnehin nicht
geheim zu halten), die Datei ist rund 1,5 KB gross und die EZB ist für
Euro-Umrechnungen die naheliegende amtliche Quelle. Die Kurse werden einmal
pro Tag geholt und im Benutzerprofil zwischengespeichert; ohne Netz rechnet
die App mit dem zuletzt bekannten Kurs weiter, statt auszufallen.
"""

import json
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from bookscouter.config import KURS_CACHE_PATH
from bookscouter.http import hole

EZB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

# Innerhalb eines Programmlaufs wird höchstens einmal abgerufen. `_kurse` ist
# der geladene Stand, `_abgerufen` merkt sich den bereits erfolgten Versuch –
# ohne dieses Flag würde eine Sammelabfrage bei fehlendem Netz für jedes Buch
# erneut in den Timeout laufen.
_kurse: dict[str, float] | None = None
_abgerufen = False


def in_euro(betrag: float, waehrung: str | None) -> float | None:
    """Rechnet einen Betrag in Euro um.

    Euro-Beträge kommen unverändert zurück, ohne dass ein Kurs nötig wäre –
    für die weit überwiegende Mehrheit der Shops passiert hier also nichts.
    `None` bedeutet "nicht umrechenbar": unbekannte Währung, oder es war noch
    nie ein Kurs zu holen. Der Aufrufer meldet den Titel dann lieber als nicht
    gefunden, als einen Franken-Betrag als Euro-Preis auszugeben.
    """
    if waehrung is None:
        return None
    waehrung = waehrung.strip().upper()
    if waehrung == "EUR":
        return float(betrag)

    kurs = _hole_kurse().get(waehrung)
    if not kurs:
        return None
    # Die EZB notiert, wie viel Fremdwährung ein Euro kostet – also geteilt,
    # nicht multipliziert.
    return float(betrag) / kurs


def _hole_kurse() -> dict[str, float]:
    """Liefert die Kurstabelle, höchstens ein Netzabruf pro Programmlauf."""
    global _kurse, _abgerufen

    if _kurse is not None:
        return _kurse

    zwischenspeicher = _lies_zwischenspeicher()
    # Verglichen wird der Tag des Abrufs, nicht das Kursdatum der EZB: die
    # veröffentlicht an Wochenenden und Feiertagen nichts, ihr `time` bleibt
    # dann auf dem letzten Werktag stehen. Gegen `heute` geprüft käme dieser
    # Stand nie als aktuell durch und die App würde an jedem Samstag bei
    # jedem Start erneut abrufen.
    if zwischenspeicher and zwischenspeicher.get("geholt_am") == date.today().isoformat():
        _kurse = zwischenspeicher["kurse"]
        return _kurse

    if not _abgerufen:
        _abgerufen = True
        frisch = _lade_von_ezb()
        if frisch is not None:
            _schreibe_zwischenspeicher(frisch)
            _kurse = frisch["kurse"]
            return _kurse

    # Kein Netz oder unbrauchbare Antwort: lieber mit dem letzten bekannten
    # Kurs rechnen als gar nicht. Buchpreise ändern sich langsamer als
    # Wechselkurse schwanken, ein paar Tage alter Kurs ist hier unkritisch.
    _kurse = zwischenspeicher["kurse"] if zwischenspeicher else {}
    return _kurse


def _lade_von_ezb() -> dict | None:
    """Holt die Tagesreferenzkurse und zerlegt sie. Wirft nie."""
    try:
        antwort = hole(EZB_URL)
        if not antwort.ok:
            return None
        wurzel = ElementTree.fromstring(antwort.text)
    except Exception:
        # Netzfehler, Timeout, kaputtes XML – ein fehlender Kurs darf die
        # Suche nicht kippen, er kostet nur diesen einen Shop.
        return None

    # Die Datei verschachtelt gleichnamige <Cube>-Elemente in einem
    # Default-Namespace. Statt mit Namespace-Präfixen zu hantieren, werden
    # schlicht alle Elemente durchgegangen und die interessanten Attribute
    # eingesammelt – das bleibt auch dann heil, wenn die EZB die Struktur
    # umbaut, solange die Attributnamen gleich bleiben.
    kurse: dict[str, float] = {}
    datum = None
    for element in wurzel.iter():
        if element.get("time"):
            datum = element.get("time")
        waehrung, kurs = element.get("currency"), element.get("rate")
        if waehrung and kurs:
            try:
                kurse[waehrung.upper()] = float(kurs)
            except ValueError:
                continue

    if not kurse:
        return None
    # `datum` ist der Kursstichtag der EZB (rein informativ, für einen Blick
    # in die Datei), `geholt_am` steuert, wann erneut abgerufen wird.
    return {
        "geholt_am": date.today().isoformat(),
        "datum": datum,
        "kurse": kurse,
    }


def _lies_zwischenspeicher() -> dict | None:
    try:
        daten = json.loads(Path(KURS_CACHE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(daten, dict) and isinstance(daten.get("kurse"), dict):
        return daten
    return None


def _schreibe_zwischenspeicher(daten: dict) -> None:
    try:
        pfad = Path(KURS_CACHE_PATH)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(daten), encoding="utf-8")
    except OSError:
        # Kein Schreibrecht: dann eben jeden Lauf neu holen. Kein Grund,
        # deshalb die Umrechnung scheitern zu lassen.
        pass
