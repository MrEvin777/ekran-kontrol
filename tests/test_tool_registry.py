import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arkana_v2  # noqa: E402
import tool_registry  # noqa: E402


def test_registry_covers_every_real_tool():
    reg = tool_registry.build_registry()
    names = {e["name"] for e in reg}
    real_names = {s["function"]["name"] for s in arkana_v2.TOOL_SCHEMAS}
    assert names == real_names


def test_confirm_required_tools_are_marked_onay_gerekli():
    reg = tool_registry.build_registry()
    by_name = {e["name"]: e for e in reg}
    for name in arkana_v2.CONFIRM_REQUIRED:
        assert by_name[name]["permission_level"] == "onay_gerekli"


def test_get_tool_returns_real_entry():
    entry = tool_registry.get_tool("run_command")
    assert entry is not None
    assert entry["risk_level"] == "yuksek"
    assert entry["permission_level"] == "onay_gerekli"


def test_get_tool_returns_none_for_unknown():
    assert tool_registry.get_tool("bilinmeyen_arac_xyz") is None
