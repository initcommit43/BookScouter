"""Normalisierung der ISBN-Eingabe.

ISBNs werden oft mit Bindestrichen oder Leerzeichen kopiert
("978-3-546-10033-5"). Morawa braucht aber die reine Ziffernfolge in der
URL, daher wird die Eingabe an einer Stelle vereinheitlicht – für CLI und UI
gleichermaßen, damit auch in der Datenbank nur eine Schreibweise landet.
"""


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
