"""Real diagnostics tests -- run the actual checks against this machine, not
mocks. This machine is expected to pass all of them (that's the point of
running the checks after fixing everything else this session)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import setup_check  # noqa: E402


def test_check_python_deps_passes_on_this_machine():
    ok, detail = setup_check.check_python_deps()
    assert ok is True, detail


def test_check_tesseract_passes_on_this_machine():
    ok, detail = setup_check.check_tesseract()
    assert ok is True, detail


def test_check_playwright_browser_passes_on_this_machine():
    ok, detail = setup_check.check_playwright_browser()
    assert ok is True, detail


def test_check_git_passes_on_this_machine():
    ok, detail = setup_check.check_git()
    assert ok is True, detail


def test_check_microphone_does_not_raise():
    # Result depends on real hardware presence -- assert it completes cleanly,
    # not a specific outcome (a CI box or a muted laptop may have 0 input devices).
    ok, detail = setup_check.check_microphone()
    assert isinstance(ok, bool)
    assert isinstance(detail, str)


def test_check_screen_capture_passes_on_this_machine():
    ok, detail = setup_check.check_screen_capture()
    assert ok is True, detail


def test_run_all_returns_one_entry_per_check_with_the_right_shape():
    results = setup_check.run_all()
    assert len(results) == 7
    for r in results:
        assert set(r.keys()) == {"name", "ok", "detail"}
        assert isinstance(r["ok"], bool)


def test_a_check_that_raises_is_reported_as_failed_not_propagated():
    result = setup_check._check("bilerek-bozuk", lambda: (_ for _ in ()).throw(RuntimeError("kasitli")))
    assert result["ok"] is False
    assert "kasitli" in result["detail"]
