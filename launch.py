"""Jarvis single entry point: "uygulama acildigi anda tum gerekli servisler
hazirlanacak" -- this is that preparation step, then it starts the app.

Ensures Ollama (the mandatory local fallback) is actually running, logs a
startup diagnostic snapshot (non-fatal -- a failed check here never blocks
launch, it's for the Kurulum Kontrolu panel / a human to review later), then
starts JarvisApp. Nothing here runs at Windows logon; this only runs when a
human double-clicks the launcher (see OmniAI_Ekran_Kontrol_Baslat.vbs).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STARTUP_LOG = Path.home() / ".omniai" / "startup_log.jsonl"
LOCK_FILE = Path.home() / ".omniai" / "jarvis.lock"


def acquire_single_instance_lock() -> bool:
    """Refuses a second launch while one is already running -- multiple
    instances each auto-speaking answers over each other was a real, reported
    bug. Stale lock (process from the pid is gone) is cleaned up and retried."""
    import psutil

    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if psutil.pid_exists(old_pid):
                return False
        except Exception:
            pass
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_single_instance_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def ensure_ollama_running(timeout_s: float = 10.0) -> bool:
    import requests

    def _up() -> bool:
        try:
            return requests.get("http://localhost:11434/api/version", timeout=2).status_code == 200
        except Exception:
            return False

    if _up():
        return True
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          creationflags=creationflags)
    except Exception:
        return False
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _up():
            return True
        time.sleep(0.5)
    return False


def run_preflight_and_log() -> list[dict]:
    sys.path.insert(0, str(HERE))
    import setup_check

    results = setup_check.run_all()
    STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), "checks": results}
    with open(STARTUP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return results


def main() -> None:
    sys.path.insert(0, str(HERE))
    if not acquire_single_instance_lock():
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "Jarvis zaten calisiyor. Ekranin sol ustundeki yuvarlak dugmeyi kullanin.",
            "Jarvis", 0x40)
        return
    try:
        ensure_ollama_running()
        run_preflight_and_log()
        import arkana_v2

        app = arkana_v2.JarvisApp()
        app.mainloop()
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    main()
