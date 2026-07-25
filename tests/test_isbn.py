from bookscouter.isbn import normalize_isbn


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
