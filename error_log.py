"""Persistent, structured error log (JSONL) -- one line per failure, with
timestamp, category, and detail. Chat-window messages disappear when the
conversation scrolls; this survives across sessions and is grep-able.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

LOG_PATH = Path.home() / ".omniai" / "error_log.jsonl"


def log_error(category: str, detail: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), "category": category, **detail}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    try:
        import memory_db
        memory_db.record_error(category, detail)
    except Exception:
        pass


def read_recent(n: int = 50) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
