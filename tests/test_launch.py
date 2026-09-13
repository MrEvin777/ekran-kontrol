import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import launch  # noqa: E402


def test_ensure_ollama_running_reaches_the_real_local_server():
    # Ollama was started earlier this session (real server, not a mock) -- this
    # proves the "already up" fast-path actually talks to it.
    assert launch.ensure_ollama_running(timeout_s=3) is True


def test_run_preflight_and_log_writes_a_real_startup_log_entry(monkeypatch, tmp_path):
    log_path = tmp_path / "startup_log.jsonl"
    monkeypatch.setattr(launch, "STARTUP_LOG", log_path)

    results = launch.run_preflight_and_log()

    assert isinstance(results, list) and len(results) > 0
    assert log_path.exists()
    import json
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert "checks" in entry
    assert len(entry["checks"]) == len(results)
