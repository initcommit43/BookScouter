from bookscouter.isbn import normalize_isbn, parse_isbn_liste, to_isbn10, to_isbn13


def test_removes_hyphens():
    assert normalize_isbn("978-3-546-10033-5") == "9783546100335"


def test_removes_surrounding_and_inner_whitespace():
    assert normalize_isbn("  978 3546 100335 \n") == "9783546100335"


def test_plain_isbn_unchanged():
    assert normalize_isbn("9783546100335") == "9783546100335"


def test_keeps_isbn10_check_digit_x_uppercase():
    assert normalize_isbn("3-257-2295-3x") == "325722953X"


def test_empty_input():
    assert normalize_isbn("   ") == ""


def test_isbn10_converted_to_isbn13():
    # Live bei Thalia geprüft: 3831041652 und 9783831041657 sind dasselbe Buch.
    assert to_isbn13("3831041652") == "9783831041657"


def test_isbn10_with_hyphens_converted():
    assert to_isbn13("3-8310-4165-2") == "9783831041657"


def test_isbn13_passed_through_unchanged():
    assert to_isbn13("9783831041657") == "9783831041657"


def test_isbn10_with_x_check_digit_converted():
    assert to_isbn13("080442957X") == "9780804429573"


def test_nonsense_input_returned_normalized_without_raising():
    assert to_isbn13("keine-isbn") == "KEINEISBN"


def test_isbn13_converted_to_isbn10():
    assert to_isbn10("9783831041657") == "3831041652"


def test_isbn13_with_x_check_digit_converted_to_isbn10():
    assert to_isbn10("9780804429573") == "080442957X"


def test_isbn10_passed_through_unchanged():
    assert to_isbn10("3831041652") == "3831041652"


def test_isbn10_with_hyphens_normalized_and_passed_through():
    assert to_isbn10("3-8310-4165-2") == "3831041652"


def test_isbn13_with_979_prefix_has_no_isbn10_equivalent():
    assert to_isbn10("9791234567896") is None


def test_nonsense_input_returns_none():
    assert to_isbn10("keine-isbn") is None


def test_parse_liste_zeilenweise():
    text = "9783546100335\n978-3-8310-4165-7\n"

    assert parse_isbn_liste(text) == ["9783546100335", "9783831041657"]


def test_parse_liste_gemischte_trenner():
    """Zeilenumbruch, Komma und Semikolon dürfen gemischt vorkommen."""
    text = "9783546100335, 9783831041657; 9780804429573"

    assert parse_isbn_liste(text) == [
        "9783546100335", "9783831041657", "9780804429573",
    ]


def test_parse_liste_nur_leerzeichen_als_trenner():
    """Mehrere ISBNs in einer Zeile, nur durch Leerzeichen getrennt."""
    text = "9783546100335 9783831041657"

    assert parse_isbn_liste(text) == ["9783546100335", "9783831041657"]


def test_parse_liste_leerzeichen_innerhalb_einer_isbn_bleiben_erhalten():
    """"978 3546 100335" ist eine ISBN, nicht drei."""
    assert parse_isbn_liste("978 3546 100335") == ["9783546100335"]


def test_parse_liste_wandelt_isbn10_um():
    assert parse_isbn_liste("3831041652") == ["9783831041657"]


def test_parse_liste_entfernt_dubletten_auch_ueber_schreibweisen():
    """Derselbe Band als ISBN-10 und ISBN-13 ist ein Buch, nicht zwei."""
    text = "3831041652\n9783831041657\n978-3-8310-4165-7"

    assert parse_isbn_liste(text) == ["9783831041657"]


def test_parse_liste_behaelt_eingabereihenfolge():
    """Die Reihenfolge ist später die Reihenfolge der Ergebnisblöcke."""
    text = "9780804429573\n9783546100335\n9783831041657"

    assert parse_isbn_liste(text) == [
        "9780804429573", "9783546100335", "9783831041657",
    ]


def test_parse_liste_ignoriert_leerzeilen():
    text = "\n9783546100335\n\n   \n9783831041657\n\n"

    assert parse_isbn_liste(text) == ["9783546100335", "9783831041657"]


def test_parse_liste_leere_eingabe():
    assert parse_isbn_liste("   \n\n") == []


def test_parse_liste_reicht_unsinn_durch():
    """Nicht stillschweigend verschlucken: sonst fehlt eine Zeile
    kommentarlos im Ergebnis, statt als 'nicht gefunden' aufzutauchen."""
    assert parse_isbn_liste("keine-isbn\n9783546100335") == [
        "KEINEISBN", "9783546100335",
    ]
