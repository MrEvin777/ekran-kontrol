"""Task state machine + on-disk checkpoint, so progress survives a crash or a
forced process kill (arkana_v2.py has no real "Quit" -- closing the window just
hides it -- so the failure mode this guards against is the process itself dying:
a crash, a forced kill, an OS restart, not a clean menu-driven exit).

Before this, chat_history (arkana_v2.py's only continuity mechanism) is written
ONCE, after a turn fully completes -- if the process dies mid tool-calling loop,
every tool call already made in that turn is silently lost. This module adds a
second, finer-grained checkpoint: one JSON write after every tool execution.
"""

from __future__ import annotations

import dataclasses
import json
import time
import uuid
from enum import Enum
from pathlib import Path


class TaskState(Enum):
    NEW = "NEW"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    WAITING_FOR_PERMISSION = "WAITING_FOR_PERMISSION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RETRYING = "RETRYING"
    PAUSED = "PAUSED"
    RESUMABLE = "RESUMABLE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


_VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.NEW: {TaskState.ANALYZING, TaskState.FAILED},
    TaskState.ANALYZING: {TaskState.PLANNING, TaskState.EXECUTING, TaskState.FAILED, TaskState.PAUSED},
    TaskState.PLANNING: {TaskState.WAITING_FOR_PERMISSION, TaskState.EXECUTING, TaskState.FAILED, TaskState.PAUSED},
    TaskState.WAITING_FOR_PERMISSION: {TaskState.EXECUTING, TaskState.FAILED, TaskState.PAUSED},
    TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.WAITING_FOR_PERMISSION, TaskState.FAILED,
                           TaskState.PAUSED, TaskState.RETRYING, TaskState.EXECUTING},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.RETRYING, TaskState.FAILED, TaskState.PAUSED},
    TaskState.RETRYING: {TaskState.EXECUTING, TaskState.WAITING_FOR_PERMISSION, TaskState.FAILED, TaskState.PAUSED},
    TaskState.PAUSED: {TaskState.RESUMABLE},
    TaskState.RESUMABLE: {TaskState.ANALYZING, TaskState.PLANNING, TaskState.WAITING_FOR_PERMISSION,
                           TaskState.EXECUTING, TaskState.VERIFYING, TaskState.FAILED},
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
}


class InvalidTransitionError(RuntimeError):
    pass


@dataclasses.dataclass
class Task:
    id: str
    goal: str
    state: TaskState = TaskState.NEW
    checkpoint: dict = dataclasses.field(default_factory=dict)
    created_at: float = dataclasses.field(default_factory=time.time)
    updated_at: float = dataclasses.field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["state"] = self.state.value
        return d

    @staticmethod
    def from_dict(d: dict) -> "Task":
        return Task(id=d["id"], goal=d["goal"], state=TaskState(d["state"]),
                    checkpoint=d.get("checkpoint", {}), created_at=d.get("created_at", time.time()),
                    updated_at=d.get("updated_at", time.time()))


class TaskStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create(self, goal: str) -> Task:
        task = Task(id=str(uuid.uuid4()), goal=goal)
        data = self._read()
        data[task.id] = task.to_dict()
        self._write(data)
        return task

    def get(self, task_id: str) -> Task | None:
        raw = self._read().get(task_id)
        return Task.from_dict(raw) if raw else None

    def save(self, task: Task) -> None:
        task.updated_at = time.time()
        data = self._read()
        data[task.id] = task.to_dict()
        self._write(data)
        try:
            import memory_db
            memory_db.record_task(task.id, task.goal, task.state.value, task.created_at, task.updated_at)
        except Exception:
            pass  # SQLite aynasi ikincil -- JSON dosyasi zaten gercek kaynagi, burda hata gorevi engellemez

    def list_resumable(self) -> list[Task]:
        return [t for t in (Task.from_dict(v) for v in self._read().values()) if t.state == TaskState.RESUMABLE]

    def transition(self, task_id: str, to_state: TaskState) -> Task:
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if to_state not in _VALID_TRANSITIONS.get(task.state, set()):
            raise InvalidTransitionError(f"{task.state.value} -> {to_state.value} gecersiz gecis")
        task.state = to_state
        self.save(task)
        return task

    def checkpoint(self, task_id: str, data: dict) -> Task:
        """Merge new fields into the task's checkpoint without changing its state --
        called after every tool execution, cheap enough to do unconditionally."""
        task = self.get(task_id)
        if task is None:
            raise KeyError(task_id)
        task.checkpoint.update(data)
        self.save(task)
        return task

    def mark_interrupted(self, task_id: str) -> None:
        """Best-effort: called from an atexit/close handler for a task still in
        flight, so it shows up as resumable next launch instead of vanishing."""
        task = self.get(task_id)
        if task is None or task.state in (TaskState.COMPLETED, TaskState.FAILED):
            return
        try:
            if task.state not in (TaskState.PAUSED, TaskState.RESUMABLE):
                self.transition(task_id, TaskState.PAUSED)
            self.transition(task_id, TaskState.RESUMABLE)
        except InvalidTransitionError:
            pass
