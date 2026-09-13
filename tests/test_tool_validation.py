"""Real tests for the schema-validation gate: an invalid tool call must never
reach _execute_tool's actual side-effecting branches (file writes, subprocess,
clicks, etc.) -- this is the guard against a hallucinating local model.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arkana_v2 import validate_tool_call  # noqa: E402


def test_unknown_tool_name_is_rejected():
    ok, err = validate_tool_call("delete_everything", {})
    assert ok is False
    assert "Bilinmeyen arac" in err


def test_missing_required_field_is_rejected():
    ok, err = validate_tool_call("click", {"x": 10})  # y is required
    assert ok is False
    assert "y" in err


def test_wrong_type_is_rejected():
    ok, err = validate_tool_call("click", {"x": "onehundred", "y": 20})
    assert ok is False
    assert "click.x" in err


def test_args_must_be_a_dict():
    ok, err = validate_tool_call("click", "not a dict")
    assert ok is False


def test_valid_call_passes():
    ok, err = validate_tool_call("click", {"x": 100, "y": 200})
    assert ok is True
    assert err is None


def test_valid_call_with_optional_field_passes():
    ok, err = validate_tool_call("click", {"x": 100, "y": 200, "button": "right"})
    assert ok is True


def test_delegate_to_agent_rejects_a_role_outside_the_enum():
    ok, err = validate_tool_call("delegate_to_agent", {"role": "hacker", "task": "x"})
    assert ok is False
    assert "role" in err


def test_delegate_to_agent_accepts_a_valid_role():
    ok, err = validate_tool_call("delegate_to_agent", {"role": "kodlayici", "task": "x"})
    assert ok is True


def test_get_ui_elements_requires_window_id():
    ok, err = validate_tool_call("get_ui_elements", {})
    assert ok is False
    assert "window_id" in err


def test_click_element_requires_both_fields():
    ok, err = validate_tool_call("click_element", {"window_id": 123})
    assert ok is False
    assert "name_contains" in err


def test_click_element_valid_call_passes():
    ok, err = validate_tool_call("click_element", {"window_id": 123, "name_contains": "Kaydet"})
    assert ok is True


def test_list_open_windows_takes_no_arguments():
    ok, err = validate_tool_call("list_open_windows", {})
    assert ok is True


def test_browser_navigate_requires_url():
    ok, err = validate_tool_call("browser_navigate", {})
    assert ok is False
    assert "url" in err


def test_browser_click_requires_text():
    ok, err = validate_tool_call("browser_click", {})
    assert ok is False


def test_browser_type_requires_both_fields():
    ok, err = validate_tool_call("browser_type", {"label_or_placeholder": "Adiniz"})
    assert ok is False
    assert "text" in err


def test_git_diff_requires_repo_path():
    ok, err = validate_tool_call("git_diff", {})
    assert ok is False


def test_git_diff_optional_staged_flag_accepts_valid_call():
    ok, err = validate_tool_call("git_diff", {"repo_path": "C:\\x", "staged": True})
    assert ok is True


def test_git_diff_rejects_wrong_type_for_staged():
    ok, err = validate_tool_call("git_diff", {"repo_path": "C:\\x", "staged": "yes"})
    assert ok is False
