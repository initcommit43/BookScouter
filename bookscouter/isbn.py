"""Normalisierung der ISBN-Eingabe.

ISBNs werden oft mit Bindestrichen oder Leerzeichen kopiert
("978-3-546-10033-5"). Morawa braucht aber die reine Ziffernfolge in der
URL, daher wird die Eingabe an einer Stelle vereinheitlicht – für CLI und UI
gleichermaßen, damit auch in der Datenbank nur eine Schreibweise landet.
"""

import re

# Trenner zwischen mehreren ISBNs einer Sammelabfrage. Leerzeichen stehen
# bewusst nicht dabei: sie kommen auch *innerhalb* einer ISBN vor
# ("978 3 546 10033 5"). Den Fall "mehrere ISBNs in einer Zeile, nur durch
# Leerzeichen getrennt" fängt `_zerlege()` gesondert ab.
_TRENNER = re.compile(r"[\n\r,;]+")


def normalize_isbn(raw: str) -> str:
    """Entfernt Bindestriche, Leerzeichen & Co. aus einer ISBN-Eingabe.

    Das X einer ISBN-10-Prüfziffer bleibt erhalten (in Grossbuchstaben).
    """
    return "".join(zeichen for zeichen in raw.strip() if zeichen.isalnum()).upper()


def to_isbn13(isbn: str) -> str:
    """Wandelt eine ISBN-10 in die gleichwertige ISBN-13 um.

    Wird für den Abgleich "führt diese Produktseite wirklich das gesuchte
    Buch?" gebraucht: die Shops geben in ihren Produktdaten durchweg die
    ISBN-13 an, auch wenn ihre Suche eine ISBN-10 akzeptiert (bei Thalia
    live geprüft). Ohne Umrechnung würde eine ISBN-10-Suche an diesem
    Abgleich fälschlich scheitern.

    Eingaben, die keine ISBN-10 sind, kommen unverändert zurück – die
    Prüfung bleibt damit auch bei krummen Eingaben ein reiner Vergleich
    und wirft nie.
    """
    isbn = normalize_isbn(isbn)
    if len(isbn) != 10 or not isbn[:9].isdigit():
        return isbn

    kern = "978" + isbn[:9]
    # EAN-13-Prüfziffer: Ziffern abwechselnd mit 1 und 3 gewichten.
    summe = sum(int(ziffer) * (1 if pos % 2 == 0 else 3) for pos, ziffer in enumerate(kern))
    return kern + str((10 - summe % 10) % 10)


def to_isbn10(isbn: str) -> str | None:
    """Wandelt eine ISBN-13 in die gleichwertige ISBN-10 um, falls möglich.

    Gebraucht für Amazon, das Bücher über ihre ISBN-10 als ASIN in der
    Produkt-URL adressiert (z. B. amazon.de/dp/<ISBN-10>). Nur ISBN-13 mit
    dem Präfix "978" haben überhaupt eine ISBN-10-Entsprechung – der
    979-Nummernraum wurde erst nach Einführung von ISBN-13 vergeben und hat
    keine. Anders als `to_isbn13()` liefert diese Funktion deshalb `None`
    statt der unveränderten Eingabe, wenn keine gültige ISBN-10 existiert:
    der Aufrufer baut daraus eine URL und braucht ein klares Signal, statt
    versehentlich mit einer falschen ISBN einen Request zu schicken.

    Eingaben, die bereits eine ISBN-10 sind, kommen unverändert zurück.
    """
    isbn = normalize_isbn(isbn)
    if len(isbn) == 10:
        return isbn
    if len(isbn) != 13 or not isbn.isdigit() or not isbn.startswith("978"):
        return None

    kern = isbn[3:12]
    # ISBN-10-Prüfziffer: Ziffern mit fallendem Gewicht 10..2, Summe mod 11;
    # Rest 10 wird als "X" geschrieben.
    summe = sum(int(ziffer) * gewicht for ziffer, gewicht in zip(kern, range(10, 1, -1)))
    rest = (11 - summe % 11) % 11
    pruefziffer = "X" if rest == 10 else str(rest)
    return kern + pruefziffer


def parse_isbn_liste(text: str) -> list[str]:
    """Zerlegt eine Eingabe mit mehreren ISBNs in eine Liste von ISBN-13.

    Für die Sammelabfrage: die Textbox der Oberfläche und die
    Kommandozeilen-Argumente laufen beide hier durch, damit eine Liste in
    beiden Fällen gleich verstanden wird.

    Alles wird auf ISBN-13 gebracht – derselbe Band einmal als ISBN-10 und
    einmal als ISBN-13 eingetippt ist ein Buch, nicht zwei (sonst gäbe es
    zwei Ergebnisblöcke und zwei getrennte Preisverläufe). Aus demselben
    Grund fliegen Dubletten raus; die Reihenfolge der Eingabe bleibt aber
    erhalten, denn sie ist später die Reihenfolge der Ergebnisse.

    Bewusst ohne Gültigkeitsprüfung: was keine ISBN ist, wird trotzdem
    durchgereicht und von den Shops als "nicht gefunden" beantwortet. Ein
    stillschweigend verschluckter Eintrag wäre schlimmer als eine
    ergebnislose Abfrage – die Nutzerin sähe sonst nie, dass ihre Zeile
    gefehlt hat.
    """
    isbns: list[str] = []
    for teil in _TRENNER.split(text):
        for kandidat in _zerlege(teil):
            isbn = to_isbn13(kandidat)
            if isbn and isbn not in isbns:
                isbns.append(isbn)
    return isbns


def _zerlege(teil: str) -> list[str]:
    """Ein Abschnitt zwischen zwei Trennern – meist genau eine ISBN.

    Länger als 13 Zeichen kann keine ISBN sein; dann steckt in dem Abschnitt
    in aller Wahrscheinlichkeit eine Reihe von ISBNs, die nur durch
    Leerzeichen getrennt sind ("9783546100335 9783551741035"). Erst in
    diesem Fall wird zusätzlich an Leerzeichen getrennt – so bleibt die
    innerhalb einer einzelnen ISBN erlaubte Schreibweise mit Leerzeichen
    unangetastet.
    """
    normalisiert = normalize_isbn(teil)
    if not normalisiert:
        return []
    if len(normalisiert) <= 13:
        return [teil]
    return [stueck for stueck in teil.split() if normalize_isbn(stueck)]
