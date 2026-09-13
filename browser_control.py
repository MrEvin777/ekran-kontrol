"""Browser control via Playwright.

Spec priority order for browser interaction: DOM > accessibility snapshot >
Playwright API > element reference > visual. Playwright's own role/text-based
locators (get_by_role, get_by_text) are themselves accessibility-tree lookups,
so using them (instead of raw CSS selectors or screenshot+click) satisfies
priorities 1-3 in one mechanism; get_page_text/screenshot cover the rest.

Runs a visible (non-headless) browser in its own dedicated profile directory --
NOT the user's real Chrome/Edge profile -- so Jarvis never touches their
existing logged-in sessions/cookies without being asked to. One browser/page is
kept alive across calls (module-level singleton) so navigation state persists
between tool calls in the same conversation; a lock serializes access since
tool calls can come from a background thread.
"""

from __future__ import annotations

import threading
from pathlib import Path

_lock = threading.Lock()
_state = {"playwright": None, "context": None, "page": None}

PROFILE_DIR = Path.home() / ".omniai" / "browser_profile"


def _ensure_started():
    if _state["page"] is not None:
        return
    from playwright.sync_api import sync_playwright

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    try:
        context = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, channel="chrome"
        )
    except Exception:
        # "chrome" channel needs a system Chrome install; fall back to the
        # Playwright-bundled Chromium if it's not present.
        context = pw.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
    page = context.pages[0] if context.pages else context.new_page()
    _state["playwright"], _state["context"], _state["page"] = pw, context, page


def navigate(url: str) -> dict:
    with _lock:
        _ensure_started()
        page = _state["page"]
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        return {"ok": True, "url": page.url, "title": page.title()}


def get_page_text(max_chars: int = 8000) -> dict:
    with _lock:
        _ensure_started()
        page = _state["page"]
        text = page.inner_text("body")
        return {"ok": True, "url": page.url, "text": text[:max_chars]}


def click_by_text(text: str) -> dict:
    """Clicks the first visible element whose accessible name/text matches --
    tries role-based (button/link) locators first, then a plain text locator."""
    with _lock:
        _ensure_started()
        page = _state["page"]
        for locator in (
            page.get_by_role("button", name=text, exact=False),
            page.get_by_role("link", name=text, exact=False),
            page.get_by_text(text, exact=False),
        ):
            try:
                if locator.count() > 0:
                    locator.first.click(timeout=5000)
                    return {"ok": True, "clicked": text}
            except Exception:
                continue
        return {"ok": False, "error": f"'{text}' ile eslesen tiklanabilir bir eleman bulunamadi."}


def type_into(label_or_placeholder: str, text: str) -> dict:
    with _lock:
        _ensure_started()
        page = _state["page"]
        for locator in (
            page.get_by_label(label_or_placeholder, exact=False),
            page.get_by_placeholder(label_or_placeholder, exact=False),
        ):
            try:
                if locator.count() > 0:
                    locator.first.fill(text, timeout=5000)
                    return {"ok": True, "field": label_or_placeholder}
            except Exception:
                continue
        return {"ok": False, "error": f"'{label_or_placeholder}' ile eslesen bir giris alani bulunamadi."}


def screenshot(out_path: str) -> dict:
    with _lock:
        _ensure_started()
        _state["page"].screenshot(path=out_path)
        return {"ok": True, "path": out_path}


def close():
    with _lock:
        if _state["context"] is not None:
            _state["context"].close()
        if _state["playwright"] is not None:
            _state["playwright"].stop()
        _state["playwright"] = _state["context"] = _state["page"] = None
