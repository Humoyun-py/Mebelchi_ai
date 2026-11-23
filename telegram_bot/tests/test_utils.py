import pytest

from bot.services.uploads import UploadRejected, check_upload
from bot.utils.calc import InvalidNumber, parse_number
from bot.utils.i18n import TEXTS, language_for, t
from bot.utils.ratelimit import SlidingWindowLimiter


def test_translations_have_identical_keys_in_all_languages():
    keys = [set(table) for table in TEXTS.values()]
    assert all(k == keys[0] for k in keys)
    assert set(TEXTS) == {"uz", "ru", "en"}


def test_language_detection_falls_back_to_uzbek():
    assert language_for("ru-RU") == "ru"
    assert language_for("en") == "en"
    assert language_for("de") == "uz"
    assert language_for(None) == "uz"


def test_user_values_are_escaped_in_html_messages():
    text = t("project_created", "en", name="<script>x</script>")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


@pytest.mark.parametrize("text, expected", [("800", 800.0), ("18,5", 18.5), (" 16.0 ", 16.0)])
def test_parse_number_accepts_common_formats(text, expected):
    assert parse_number(text, 1, 3000) == expected


@pytest.mark.parametrize("text", ["", "abc", "nan", "inf", "5000", "0", "-3"])
def test_parse_number_rejects_bad_or_out_of_range(text):
    with pytest.raises(InvalidNumber):
        parse_number(text, 100, 3000)


def test_integer_fields_reject_fractions():
    assert parse_number("3", 0, 10, integer=True) == 3
    with pytest.raises(InvalidNumber):
        parse_number("2.5", 0, 10, integer=True)


def test_upload_accepts_valid_pdf_and_png():
    assert check_upload("drawing.pdf", b"%PDF-1.7 body", 1000).filename == "drawing.pdf"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    assert check_upload("room.png", png, 1000).filename == "room.png"


def test_upload_rejects_wrong_type_size_and_content():
    with pytest.raises(UploadRejected) as e:
        check_upload("virus.exe", b"MZ", 1000)
    assert e.value.reason == "unsupported_type"
    with pytest.raises(UploadRejected) as e:
        check_upload("big.pdf", b"%PDF-" + b"x" * 100, 50)
    assert e.value.reason == "too_large"
    with pytest.raises(UploadRejected) as e:
        check_upload("fake.pdf", b"MZ\x90\x00 executable", 1000)
    assert e.value.reason == "content_mismatch"
    with pytest.raises(UploadRejected) as e:
        check_upload("empty.pdf", b"", 1000)
    assert e.value.reason == "empty"


def test_upload_strips_path_components_from_name():
    assert check_upload("../../etc/drawing.pdf", b"%PDF-1", 1000).filename == "drawing.pdf"


def test_rate_limiter_allows_then_recovers_after_window():
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.allow(1, now=0) for _ in range(4)] == [True, True, True, False]
    assert limiter.allow(2, now=0) is True  # limits are per user
    assert limiter.allow(1, now=61) is True
