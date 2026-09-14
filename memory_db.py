"""Birlesik SQLite hafiza: gorev gecmisi, saglayici kullanim gecmisi, hata
kayitlari, kullanici tercihleri -- hepsi TEK sorgulanabilir DB'de.

task_state.py / error_log.py / provider_gateway.py'yi DEGISTIRMEZ -- onlar
kendi JSON/JSONL dosyalarina yazmaya devam eder (calisan kod), bu modul
sadece onlarin cagri noktalarindan da beslenen, sorgulanabilir bir ayna.
API anahtarlari/hassas veri buraya asla yazilmaz.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / ".omniai" / "memory.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_history (
    id TEXT PRIMARY KEY, goal TEXT, state TEXT, created_at REAL, updated_at REAL
);
CREATE TABLE IF NOT EXISTS provider_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, ts REAL, latency_s REAL, success INTEGER
);
CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, category TEXT, detail_json TEXT
);
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY, value TEXT
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def record_task(task_id: str, goal: str, state: str, created_at: float, updated_at: float) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_history (id, goal, state, created_at, updated_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (task_id, goal, state, created_at, updated_at),
        )


def record_provider_usage(provider: str, latency_s: float, success: bool) -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO provider_usage (provider, ts, latency_s, success) VALUES (?,?,?,?)",
                      (provider, time.time(), latency_s, 1 if success else 0))


def record_error(category: str, detail: dict) -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO error_log (ts, category, detail_json) VALUES (?,?,?)",
                      (time.time(), category, json.dumps(detail, ensure_ascii=False)))


def set_preference(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO preferences (key, value) VALUES (?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_preference(key: str, default: str | None = None) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return row[0] if row else default


def recent_tasks(n: int = 20) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM task_history ORDER BY updated_at DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in rows]


def provider_stats() -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT provider, COUNT(*) as calls, AVG(latency_s) as avg_latency_s, "
            "AVG(success)*100 as success_rate_pct FROM provider_usage GROUP BY provider"
        ).fetchall()
        return [dict(r) for r in rows]


def recent_errors(n: int = 20) -> list[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM error_log ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in rows]
