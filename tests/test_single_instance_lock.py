import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import launch  # noqa: E402


def test_second_acquire_in_same_process_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(launch, "LOCK_FILE", tmp_path / "jarvis.lock")
    assert launch.acquire_single_instance_lock() is True
    assert launch.acquire_single_instance_lock() is False
    launch.release_single_instance_lock()


def test_lock_is_reacquirable_after_release(monkeypatch, tmp_path):
    monkeypatch.setattr(launch, "LOCK_FILE", tmp_path / "jarvis.lock")
    launch.acquire_single_instance_lock()
    launch.release_single_instance_lock()
    assert launch.acquire_single_instance_lock() is True
    launch.release_single_instance_lock()


def test_stale_lock_from_a_dead_pid_is_reclaimed(monkeypatch, tmp_path):
    lock = tmp_path / "jarvis.lock"
    lock.write_text("999999999")  # a pid that (almost certainly) does not exist
    monkeypatch.setattr(launch, "LOCK_FILE", lock)
    assert launch.acquire_single_instance_lock() is True
    launch.release_single_instance_lock()
