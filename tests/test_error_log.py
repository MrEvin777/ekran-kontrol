import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import error_log  # noqa: E402


def test_log_error_writes_a_real_jsonl_line(tmp_path, monkeypatch):
    log_path = tmp_path / "error_log.jsonl"
    monkeypatch.setattr(error_log, "LOG_PATH", log_path)

    error_log.log_error("tool_failure", {"tool": "run_command", "error": "timeout"})

    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    import json
    entry = json.loads(lines[0])
    assert entry["category"] == "tool_failure"
    assert entry["tool"] == "run_command"
    assert "ts" in entry


def test_read_recent_returns_most_recent_entries_in_order(tmp_path, monkeypatch):
    log_path = tmp_path / "error_log.jsonl"
    monkeypatch.setattr(error_log, "LOG_PATH", log_path)

    for i in range(5):
        error_log.log_error("provider_failure", {"provider": f"p{i}"})

    recent = error_log.read_recent(n=3)
    assert len(recent) == 3
    assert [e["provider"] for e in recent] == ["p2", "p3", "p4"]


def test_read_recent_on_missing_file_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(error_log, "LOG_PATH", tmp_path / "does_not_exist.jsonl")
    assert error_log.read_recent() == []
