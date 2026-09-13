"""Windows UI Automation: window enumeration + element role/name/automation-id.

Spec priority order for computer control is:
  1. Windows UI Automation   <- this module
  2. window/app state        <- this module (list_windows / active window)
  3. element role/name/id    <- this module (get_ui_elements)
  4. screenshot
  5. OCR
  6. mouse/keyboard coordinates (last resort)

arkana_v2.py already has 4-6 (screen_controller.py / ocr_screen / click,type,hotkey)
but nothing for 1-3 -- every interaction is coordinate-guessing from a screenshot.
This module fills that gap so a tool call can target "the Save button" by name
instead of guessing (x, y) from a JPEG.
"""

from __future__ import annotations

import dataclasses

import win32gui
import win32process


@dataclasses.dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    rect: tuple[int, int, int, int]


def list_windows(visible_only: bool = True) -> list[WindowInfo]:
    results: list[WindowInfo] = []

    def _cb(hwnd, _extra):
        if visible_only and not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        results.append(WindowInfo(hwnd=hwnd, title=title, pid=pid, rect=win32gui.GetWindowRect(hwnd)))
        return True

    win32gui.EnumWindows(_cb, None)
    return results


def get_active_window_info() -> WindowInfo | None:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return WindowInfo(hwnd=hwnd, title=title, pid=pid, rect=win32gui.GetWindowRect(hwnd))


@dataclasses.dataclass
class UiElement:
    control_type: str
    name: str
    automation_id: str
    depth: int
    rect: tuple[int, int, int, int] | None = None


def get_ui_elements(hwnd: int, max_depth: int = 3, max_elements: int = 150) -> list[UiElement]:
    """Walks the UI Automation tree of one window. Each element carries its role
    (control_type), visible name, and automation_id -- enough to target a click
    or a text-entry by "what it is" instead of by pixel position.
    """
    from pywinauto import Desktop

    window = Desktop(backend="uia").window(handle=hwnd)
    out: list[UiElement] = []

    def _walk(elem, depth: int) -> None:
        if len(out) >= max_elements or depth > max_depth:
            return
        try:
            info = elem.element_info
            rect = None
            try:
                r = info.rectangle
                rect = (r.left, r.top, r.right, r.bottom)
            except Exception:
                pass
            out.append(UiElement(control_type=info.control_type or "", name=info.name or "",
                                  automation_id=info.automation_id or "", depth=depth, rect=rect))
        except Exception:
            return
        try:
            for child in elem.children():
                _walk(child, depth + 1)
        except Exception:
            pass

    _walk(window, 0)
    return out


def find_element_by_name(hwnd: int, name_substring: str, max_depth: int = 4) -> UiElement | None:
    """Convenience lookup: first element whose name contains name_substring
    (case-insensitive). Returns None if nothing matches -- caller falls back to
    OCR/coordinates, per the spec's stated priority order.
    """
    needle = name_substring.lower()
    for el in get_ui_elements(hwnd, max_depth=max_depth, max_elements=500):
        if needle in el.name.lower():
            return el
    return None
