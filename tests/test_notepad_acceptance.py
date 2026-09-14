"""The spec's literal acceptance test: open Notepad, type text, screenshot,
verify via real OCR the text is visible, close Notepad without saving."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from computer_use import ComputerUse  # noqa: E402

EXPECTED_TEXT = "Evin AI OS calisiyor"


def test_notepad_open_type_screenshot_verify():
    cu = ComputerUse()
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1.5)

    cu.type_text(EXPECTED_TEXT)
    time.sleep(0.5)

    result = cu.verify_result(EXPECTED_TEXT)

    # Windows 11 Notepad re-spawns under its own process (the Popen pid is a
    # launcher stub), so kill by image name to actually close the real window.
    subprocess.run(["taskkill", "/F", "/IM", "notepad.exe"], capture_output=True)

    assert result["found"] is True, f"OCR metni bulamadi. Okunan: {result['text'][:300]}"
