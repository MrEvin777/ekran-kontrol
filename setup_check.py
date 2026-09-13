"""Startup/setup diagnostics -- the "ilk kurulum kontrolu" screen's logic.

Deliberately kept free of tkinter so it can run (and be tested) headless. Each
check returns {"name", "ok", "detail"} -- never raises, so one broken check
can't take the whole diagnostic run down with it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import compat  # noqa: F401  (Python 3.13+ shims -- must run before pytesseract is imported anywhere)


def _check(name, fn):
    try:
        ok, detail = fn()
        return {"name": name, "ok": ok, "detail": detail}
    except Exception as e:
        return {"name": name, "ok": False, "detail": str(e)}


def check_python_deps():
    modules = ["anthropic", "openai", "requests", "pyautogui", "PIL", "mcp", "qdrant_client",
               "sounddevice", "soundfile", "pywinauto", "win32gui", "pytesseract", "playwright"]
    missing = []
    for mod in modules:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if missing:
        return False, f"eksik paketler: {', '.join(missing)} (pip install -r requirements.txt)"
    return True, f"{len(modules)} paket kurulu"


def check_ollama():
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            n = len(r.json().get("models", []))
            return True, f"calisiyor, {n} model kurulu"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"ulasilamiyor ({e}) -- yerel yedek modeller devre disi kalir"


def check_tesseract():
    exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if not exe.exists():
        return False, "Tesseract-OCR kurulu degil (winget install UB-Mannheim.TesseractOCR)"
    user_tessdata = Path.home() / ".omniai" / "tessdata"
    has_tur = (user_tessdata / "tur.traineddata").exists()
    has_eng = (user_tessdata / "eng.traineddata").exists() or \
        (exe.parent / "tessdata" / "eng.traineddata").exists()
    if has_tur and has_eng:
        return True, "motor + tur+eng dil paketleri hazir"
    missing = [n for n, present in (("tur", has_tur), ("eng", has_eng)) if not present]
    return False, f"motor kurulu ama dil paketi eksik: {', '.join(missing)}"


def check_playwright_browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = Path(p.chromium.executable_path)
            if exe.exists():
                return True, "chromium hazir"
            return False, "chromium indirilmemis (python -m playwright install chromium)"
    except Exception as e:
        return False, str(e)


def check_git():
    if shutil.which("git") is None:
        return False, "git PATH'te bulunamadi"
    proc = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
    return proc.returncode == 0, proc.stdout.strip() or proc.stderr.strip()


def check_microphone():
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        if inputs:
            return True, f"{len(inputs)} giris cihazi bulundu"
        return False, "mikrofon girisi bulunamadi"
    except Exception as e:
        return False, str(e)


def check_screen_capture():
    import pyautogui
    img = pyautogui.screenshot()
    ok = img.size[0] > 0 and img.size[1] > 0
    return ok, f"{img.size[0]}x{img.size[1]}" if ok else "ekran goruntusu alinamadi"


def run_all():
    """Runs every check and returns the list -- order matches the spec's own
    test list (deps, local model, screen, OCR/browser are covered elsewhere,
    terminal/git, mic)."""
    return [
        _check("Bagimlilik kontrolu", check_python_deps),
        _check("Yerel model (Ollama)", check_ollama),
        _check("OCR (Tesseract)", check_tesseract),
        _check("Tarayici (Playwright)", check_playwright_browser),
        _check("Terminal/Git", check_git),
        _check("Mikrofon", check_microphone),
        _check("Ekran yakalama", check_screen_capture),
    ]
