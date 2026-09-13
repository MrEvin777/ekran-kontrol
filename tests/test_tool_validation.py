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
