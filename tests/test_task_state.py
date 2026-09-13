import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from task_state import InvalidTransitionError, TaskState, TaskStore  # noqa: E402


def test_new_task_starts_in_new_state(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    task = store.create("test hedefi")
    assert task.state == TaskState.NEW


def test_realistic_happy_path(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    task = store.create("dosya duzenle")
    store.transition(task.id, TaskState.ANALYZING)
    store.transition(task.id, TaskState.EXECUTING)
    store.transition(task.id, TaskState.VERIFYING)
    final = store.transition(task.id, TaskState.COMPLETED)
    assert final.state == TaskState.COMPLETED


def test_illegal_transition_rejected(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    task = store.create("x")
    with pytest.raises(InvalidTransitionError):
        store.transition(task.id, TaskState.COMPLETED)  # NEW -> COMPLETED skips everything


def test_checkpoint_survives_process_restart_simulation(tmp_path):
    db = tmp_path / "tasks.json"
    store_a = TaskStore(db)
    task = store_a.create("uzun gorev")
    store_a.transition(task.id, TaskState.ANALYZING)
    store_a.transition(task.id, TaskState.EXECUTING)
    store_a.checkpoint(task.id, {"last_tool": "write_file", "step": 1})
    store_a.checkpoint(task.id, {"last_tool": "run_command", "step": 2})

    # "process kill": brand new TaskStore instance, same file
    store_b = TaskStore(db)
    reloaded = store_b.get(task.id)
    assert reloaded.state == TaskState.EXECUTING
    assert reloaded.checkpoint["last_tool"] == "run_command"
    assert reloaded.checkpoint["step"] == 2


def test_mark_interrupted_makes_an_in_flight_task_resumable(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    task = store.create("x")
    store.transition(task.id, TaskState.ANALYZING)
    store.transition(task.id, TaskState.EXECUTING)

    store.mark_interrupted(task.id)

    resumable = store.list_resumable()
    assert len(resumable) == 1
    assert resumable[0].id == task.id


def test_mark_interrupted_is_a_noop_for_a_completed_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    task = store.create("x")
    store.transition(task.id, TaskState.ANALYZING)
    store.transition(task.id, TaskState.EXECUTING)
    store.transition(task.id, TaskState.VERIFYING)
    store.transition(task.id, TaskState.COMPLETED)

    store.mark_interrupted(task.id)

    assert store.get(task.id).state == TaskState.COMPLETED
    assert store.list_resumable() == []


def test_waiting_for_permission_round_trip(tmp_path):
    """Models the real flow: EXECUTING -> a risky tool call needs approval ->
    WAITING_FOR_PERMISSION -> user answers -> back to EXECUTING."""
    store = TaskStore(tmp_path / "tasks.json")
    task = store.create("git push yap")
    store.transition(task.id, TaskState.ANALYZING)
    store.transition(task.id, TaskState.EXECUTING)
    store.transition(task.id, TaskState.WAITING_FOR_PERMISSION)
    resumed = store.transition(task.id, TaskState.EXECUTING)
    assert resumed.state == TaskState.EXECUTING
