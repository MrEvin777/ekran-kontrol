import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory_db  # noqa: E402


def _use_temp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_db, "DB_PATH", tmp_path / "memory.db")


def test_record_and_read_task(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    memory_db.record_task("t1", "test hedefi", "EXECUTING", 100.0, 100.0)
    memory_db.record_task("t1", "test hedefi", "COMPLETED", 100.0, 200.0)  # ayni id -> guncelleme
    tasks = memory_db.recent_tasks()
    assert len(tasks) == 1
    assert tasks[0]["state"] == "COMPLETED"


def test_provider_stats_aggregates_real_calls(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    memory_db.record_provider_usage("groq", 0.5, True)
    memory_db.record_provider_usage("groq", 1.5, True)
    memory_db.record_provider_usage("groq", 2.0, False)
    stats = {s["provider"]: s for s in memory_db.provider_stats()}
    assert stats["groq"]["calls"] == 3
    assert round(stats["groq"]["success_rate_pct"], 1) == round(200 / 3, 1)


def test_error_log_roundtrip(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    memory_db.record_error("tool_failure", {"tool": "run_command", "error": "timeout"})
    errors = memory_db.recent_errors()
    assert len(errors) == 1
    assert errors[0]["category"] == "tool_failure"
    assert "run_command" in errors[0]["detail_json"]


def test_preferences_roundtrip(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)
    assert memory_db.get_preference("dil", "bilinmiyor") == "bilinmiyor"
    memory_db.set_preference("dil", "turkce")
    assert memory_db.get_preference("dil") == "turkce"


def test_task_store_actually_mirrors_into_sqlite(monkeypatch, tmp_path):
    """Gercek entegrasyon: task_state.TaskStore.save() sqlite'a da yaziyor mu?"""
    import task_state
    _use_temp_db(monkeypatch, tmp_path)
    store = task_state.TaskStore(tmp_path / "tasks.json")
    task = store.create("gercek entegrasyon testi")
    store.transition(task.id, task_state.TaskState.ANALYZING)
    rows = memory_db.recent_tasks()
    assert any(r["id"] == task.id and r["state"] == "ANALYZING" for r in rows)
