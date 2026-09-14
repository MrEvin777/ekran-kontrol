"""ComputerUse: formal PyAutoGUI wrapper. Does not replace screen_controller.py /
arkana_v2.py's existing click/type_text/hotkey/scroll/ocr_screen tools -- wraps
the same underlying PyAutoGUI + Tesseract calls behind one class so orchestrator
code has a single, typed interface to depend on.
"""

from __future__ import annotations

import compat  # noqa: F401  (pytesseract py3.13+ shim)
import pyautogui
import pytesseract

pyautogui.FAILSAFE = True

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_TESSDATA_DIR = None
import os as _os  # noqa: E402

_user_tessdata = _os.path.expanduser(r"~\.omniai\tessdata")
if _os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
if _os.path.isdir(_user_tessdata):
    _TESSDATA_DIR = _user_tessdata


class ComputerUse:
    def screenshot(self):
        return pyautogui.screenshot()

    def click(self, x, y):
        pyautogui.click(x, y)
        return {"ok": True, "x": x, "y": y}

    def double_click(self, x, y):
        pyautogui.doubleClick(x, y)
        return {"ok": True, "x": x, "y": y}

    def type_text(self, text):
        pyautogui.write(text)
        return {"ok": True, "chars": len(text)}

    def press(self, key):
        pyautogui.press(key)
        return {"ok": True, "key": key}

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)
        return {"ok": True, "keys": keys}

    def move(self, x, y):
        pyautogui.moveTo(x, y)
        return {"ok": True, "x": x, "y": y}

    def scroll(self, amount):
        pyautogui.scroll(amount)
        return {"ok": True, "amount": amount}

    def get_screen_state(self):
        try:
            import ui_automation
            win = ui_automation.get_active_window_info()
            active = win.title if win else None
        except Exception:
            active = None
        w, h = pyautogui.size()
        return {"active_window": active, "screen_width": w, "screen_height": h}

    def verify_result(self, expected_text=None):
        """Real OCR check -- not a guess. Returns {ok, found, text}."""
        img = self.screenshot()
        config = f'--tessdata-dir "{_TESSDATA_DIR}"' if _TESSDATA_DIR else ""
        text = pytesseract.image_to_string(img, lang="tur+eng", config=config)
        if expected_text is None:
            return {"ok": True, "found": None, "text": text}
        found = expected_text.lower() in text.lower()
        return {"ok": found, "found": found, "text": text}
