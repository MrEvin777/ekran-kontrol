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
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STARTUP_LOG = Path.home() / ".omniai" / "startup_log.jsonl"


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
    ensure_ollama_running()
    run_preflight_and_log()
    import arkana_v2

    app = arkana_v2.JarvisApp()
    app.mainloop()


if __name__ == "__main__":
    main()
