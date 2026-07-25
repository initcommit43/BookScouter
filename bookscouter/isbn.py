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
