"""Real tests against the live Windows desktop -- no mocks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ui_automation  # noqa: E402


def test_list_windows_finds_real_windows():
    wins = ui_automation.list_windows()
    assert len(wins) > 0
    assert all(w.hwnd > 0 for w in wins)
    assert any(w.title for w in wins)


def test_get_active_window_info_returns_a_real_window():
    win = ui_automation.get_active_window_info()
    assert win is not None
    assert win.hwnd > 0
    assert win.pid > 0


def test_get_ui_elements_walks_the_active_window_without_crashing():
    win = ui_automation.get_active_window_info()
    elements = ui_automation.get_ui_elements(win.hwnd, max_depth=2, max_elements=50)
    assert isinstance(elements, list)
    for el in elements:
        assert isinstance(el.control_type, str)
        assert isinstance(el.depth, int)


def test_find_element_by_name_returns_none_for_nonsense_query():
    win = ui_automation.get_active_window_info()
    result = ui_automation.find_element_by_name(win.hwnd, "xyz_this_will_never_match_anything_zzz")
    assert result is None
