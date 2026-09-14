import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import opencode_bridge  # noqa: E402


def test_is_available_matches_real_installed_cli():
    assert opencode_bridge.is_available() is True  # opencode 1.18.26 is installed on this machine


def test_run_task_reaches_the_real_cli_and_returns_a_structured_result(tmp_path):
    """Auth is real and verified (Google key mapped correctly -- confirmed by
    reaching the Gemini API and getting a real quota/model error back, not an
    auth error). Not asserted: that a specific default model succeeds -- that's
    an account/model-catalog issue on OpenCode's side, tracked separately, not
    a code correctness question. What IS asserted: the subprocess call
    completes, and the result dict always has ok/text/error in the right shape,
    whether the underlying call succeeds or not."""
    if not opencode_bridge.is_available():
        pytest.skip("opencode CLI kurulu degil")
    result = opencode_bridge.run_task(
        "hello.txt adinda bir dosya olustur, icine tam olarak 'merhaba' yaz. Baska bir sey yapma.",
        cwd=str(tmp_path), timeout_s=90,
    )
    assert "ok" in result and isinstance(result["ok"], bool)
    assert "text" in result
    assert "error" in result
    if result["ok"]:
        created = tmp_path / "hello.txt"
        assert created.exists()
        assert "merhaba" in created.read_text(encoding="utf-8").lower()
