"""The spec's explicit "ornek gorev testi" requirement: a real end-to-end run --
user message in, real provider call, real task-state progression out. Uses
Ollama only (app.config_data is cleared so no real/paid API key is touched),
and redirects chat history + the task store to tmp_path so the user's real
saved state is never written to.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import arkana_v2  # noqa: E402
from task_state import TaskState, TaskStore  # noqa: E402


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    # Must patch the CLASS attribute BEFORE construction: __init__ calls
    # _load_chat_history() itself, which reads self.CHAT_HISTORY_FILE -- setting
    # it on the instance AFTER construction is too late and silently loads the
    # user's real saved history into memory (a real bug this test caught).
    monkeypatch.setattr(arkana_v2.JarvisApp, "CHAT_HISTORY_FILE", tmp_path / "chat_history.json")
    try:
        app = arkana_v2.JarvisApp()
    except Exception as e:
        pytest.skip(f"no display available to open a Tk window here ({e})")
        return
    app.config_data = {}  # forces the fallback chain down to Ollama only -- no real key touched
    app._task_store = TaskStore(tmp_path / "tasks.json")
    yield app
    if app.live_watching:
        app._toggle_live()
    app.destroy()


def test_a_real_simple_task_completes_end_to_end_via_local_ollama(isolated_app):
    app = isolated_app
    task = app._task_store.create("basit soru")
    app._current_task_id = task.id
    app._task_transition(TaskState.ANALYZING)
    app._task_transition(TaskState.EXECUTING)

    # run synchronously (not via a background thread) so we can assert right after
    app._agent_loop("Sadece rakamla cevap ver: 7 artı 5 kac eder?", "fast")

    final_task = app._task_store.get(task.id)
    assert final_task.state == TaskState.COMPLETED
    # NOTE: measured live -- qwen2.5:3b (the local fast-tier model) does not
    # reliably skip tool-calling even for a plain arithmetic question, so the
    # message count is NOT asserted to be exactly 2 (it was observed to reach 8
    # on this machine, via real tool round-trips). What's asserted is the real,
    # model-independent contract: a user turn went in, an assistant turn with
    # real content came out, and every tool step (if any) was truly checkpointed.
    assert len(app.chat_history) >= 2
    assert app.chat_history[0]["role"] == "user"
    assert app.chat_history[-1]["role"] == "assistant"
    assert len(app.chat_history[-1]["content"]) > 0
    assert app.CHAT_HISTORY_FILE.exists()  # the isolated file, not the user's real one
    if len(app.chat_history) > 2:
        assert final_task.checkpoint.get("last_tool") is not None  # a tool really ran and was checkpointed


def test_a_task_needing_a_tool_call_reaches_a_real_terminal_state(isolated_app):
    """Small local models are not always reliable at tool-calling -- this test
    documents that honestly: it asserts the loop reaches a REAL terminal state
    (COMPLETED or FAILED) without crashing, not that the tool call necessarily
    happened. See docs note in the audit report about local-model tool-calling."""
    app = isolated_app
    task = app._task_store.create("aktif pencereyi sor")
    app._current_task_id = task.id
    app._task_transition(TaskState.ANALYZING)
    app._task_transition(TaskState.EXECUTING)

    app._agent_loop("get_active_window aracini cagirip su an hangi pencerede oldugumu soyle.", "fast")

    final_task = app._task_store.get(task.id)
    assert final_task.state in (TaskState.COMPLETED, TaskState.FAILED)
