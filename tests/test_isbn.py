from bookscouter.isbn import normalize_isbn, to_isbn10, to_isbn13


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
