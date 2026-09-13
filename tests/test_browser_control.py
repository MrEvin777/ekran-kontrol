"""Real Playwright tests -- launches an actual (visible) browser against a local
fixture page. Slower than the rest of the suite; that's expected for real
browser automation. The module-level browser is closed at the end of the file.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import browser_control  # noqa: E402

FIXTURE_URL = (Path(__file__).parent / "fixtures" / "test_page.html").resolve().as_uri()


@pytest.fixture(scope="module", autouse=True)
def _close_browser_after_module():
    yield
    browser_control.close()


def test_navigate_reaches_the_real_page():
    result = browser_control.navigate(FIXTURE_URL)
    assert result["ok"] is True
    assert "Jarvis Test Sayfasi" in result["title"]


def test_get_page_text_reads_real_dom_content():
    browser_control.navigate(FIXTURE_URL)
    result = browser_control.get_page_text()
    assert result["ok"] is True
    assert "Bu bir Jarvis tarayici testi sayfasidir." in result["text"]


def test_click_by_text_actually_clicks_the_real_button():
    browser_control.navigate(FIXTURE_URL)
    result = browser_control.click_by_text("Tikla Beni")
    assert result["ok"] is True
    after = browser_control.get_page_text()
    assert "Tiklandi!" in after["text"]  # proves the click landed, not just "no exception"


def test_type_into_fills_the_real_input_by_label():
    browser_control.navigate(FIXTURE_URL)
    result = browser_control.type_into("Adiniz", "Muslum")
    assert result["ok"] is True


def test_click_by_text_returns_a_clean_error_for_no_match():
    browser_control.navigate(FIXTURE_URL)
    result = browser_control.click_by_text("Bu Metin Hicbir Yerde Yok Zzz")
    assert result["ok"] is False
    assert "bulunamadi" in result["error"]
