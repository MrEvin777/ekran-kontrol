"""Arkana Yaslan - Kisisel AI Bilgisayar Asistani (v3)

Mimari:
- Butun guclu yetenekler (tiklama, dosya, komut calistirma...) SADECE bu uygulamanin
  icinde, Python fonksiyonu olarak calisir. Disaridan (ag, n8n, baska program) hicbir
  sekilde tetiklenemez - boyle bir "arka kapi" bilerek yok.
- Riskli olmayan islemler (tiklama, yazma, dosya okuma, yeni dosya olusturma...) hemen
  calisir. Sadece gercekten kritik/geri donusu zor islemler (var olan dosyayi silme/
  ustune yazma, komut calistirma, git push, e-posta gonderme) icin onay ister.
- Her calisan arac, sohbet gecmisinde seffaf sekilde loglanir.
- Uygulama SADECE kullanici kendisi actiginda calisir (Windows acilisinda otomatik
  baslamaz - bilinçli tercih).
"""
import base64
import difflib
import io
import json
import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
import uuid
import webbrowser
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog, ttk

import pyautogui
import pyperclip
import requests
from PIL import Image, ImageTk

try:
    import pygetwindow as gw
except Exception:
    gw = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import sounddevice as sd
    import soundfile as sf
except Exception:
    sd = None
    sf = None

# pytesseract 0.3.10/0.3.13 both do `from pkgutil import find_loader`, removed in
# Python 3.13+. Shim it back so `import pytesseract` (in ocr_screen) doesn't crash.
import pkgutil as _pkgutil

if not hasattr(_pkgutil, "find_loader"):
    import importlib.util as _importlib_util

    _pkgutil.find_loader = lambda name: _importlib_util.find_spec(name)

# Point pytesseract at the real tesseract.exe -- winget installs it but does not
# add it to PATH, so a bare `pytesseract.image_to_string()` fails without this.
_TESSERACT_EXE = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if _TESSERACT_EXE.exists():
    try:
        import pytesseract as _pytesseract

        _pytesseract.pytesseract.tesseract_cmd = str(_TESSERACT_EXE)
    except Exception:
        pass

pyautogui.FAILSAFE = True

HYPER_ROUTER_URL = "http://localhost:20129"
N8N_URL = "http://localhost:5678"
CONFIG_DIR = Path.home() / ".omniai"
CONFIG_FILE = CONFIG_DIR / "config.json"
LIVE_INTERVAL_SEC = 3


def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# Bu araclar HER ZAMAN onay ister (geri donusu zor / kritik)
CONFIRM_REQUIRED = {"run_command", "git_push", "send_email"}

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "click", "description": "Ekranda belirtilen x,y koordinatina tiklar.",
        "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"},
        "button": {"type": "string", "enum": ["left", "right"], "default": "left"}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "type_text", "description": "O an odaklanmis alana metin yazar.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "hotkey", "description": "Klavye kisayolu basar (orn: ctrl+c).",
        "parameters": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
        "required": ["keys"]}}},
    {"type": "function", "function": {"name": "scroll", "description": "Sayfayi yukari/asagi kaydirir.",
        "parameters": {"type": "object", "properties": {"clicks": {"type": "integer",
        "description": "pozitif=yukari, negatif=asagi"}}, "required": ["clicks"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Bir metin dosyasinin icerigini okur.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Bir dosyaya metin yazar (dosya varsa "
        "diff gosterip once onay ister).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "Bir klasordeki dosya/klasorleri listeler.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_files", "description": "Bir klasorde isim desenine gore "
        "dosya arar.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}},
        "required": ["path", "pattern"]}}},
    {"type": "function", "function": {"name": "delete_file", "description": "Bir dosyayi siler (HER ZAMAN onay "
        "ister, Geri Al ile kurtarilabilir).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Bir shell komutu calistirir (HER "
        "ZAMAN onay ister).",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "git_status", "description": "Bir git deposunun durumunu gosterir.",
        "parameters": {"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": ["repo_path"]}}},
    {"type": "function", "function": {"name": "git_commit", "description": "Degisiklikleri yerel olarak commit "
        "eder (uzak sunucuya gondermez).",
        "parameters": {"type": "object", "properties": {"repo_path": {"type": "string"}, "message": {"type": "string"}},
        "required": ["repo_path", "message"]}}},
    {"type": "function", "function": {"name": "git_push", "description": "Commit'leri uzak sunucuya gonderir (HER "
        "ZAMAN onay ister).",
        "parameters": {"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": ["repo_path"]}}},
    {"type": "function", "function": {"name": "open_url", "description": "Tarayicida bir adres acar.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "open_app", "description": "Bir programi acar (orn: notepad, calc).",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "get_clipboard", "description": "Pano icerigini okur.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "set_clipboard", "description": "Panoya metin kopyalar.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "ocr_screen", "description": "Ekrandaki yaziyi tam metin olarak "
        "okur (tahmin degil).", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "send_email", "description": "SMTP ile e-posta gonderir (HER ZAMAN "
        "onay ister, once Ayarlar'dan e-posta bilgisi girilmis olmali).",
        "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"},
        "body": {"type": "string"}}, "required": ["to", "subject", "body"]}}},
    {"type": "function", "function": {"name": "read_document", "description": "Bir PDF/Word/PowerPoint dosyasini "
        "okur (Docling).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "web_search", "description": "Bir web adresini acip icerigini "
        "okur / ozetler (Crawl4AI).",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "get_active_window", "description": "Kullanicinin su an hangi "
        "programda/pencerede oldugunu soyler.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "memory_save", "description": "Onemli bir bilgiyi, tercihi veya "
        "karari kalici hafizaya kaydeder (kullanici bilgisayari kapatsa bile hatirlanir).",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "tag": {"type": "string",
        "description": "orn: 'proje', 'tercih', 'karar'"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "memory_search", "description": "Kalici hafizada gecmiste "
        "kaydedilmis ilgili bilgileri arar.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "delegate_to_agent", "description": "Ozel bir uzman alt-ajana "
        "(arastirmaci, kodlayici veya test_uzmani) bagimsiz bir gorev devreder ve sonucunu alir. Karmasik "
        "gorevleri paralel/uzmanlasmis sekilde cozmek icin kullan.",
        "parameters": {"type": "object", "properties": {
            "role": {"type": "string", "enum": ["arastirmaci", "kodlayici", "test_uzmani"]},
            "task": {"type": "string", "description": "Alt-ajana verilecek net gorev tanimi"}},
            "required": ["role", "task"]}}},
    {"type": "function", "function": {"name": "mcp_list_tools", "description": "Bir MCP sunucusundaki mevcut "
        "araclari listeler (Ayarlar'da tanimlanmis olmali).",
        "parameters": {"type": "object", "properties": {"server_name": {"type": "string"}},
        "required": ["server_name"]}}},
    {"type": "function", "function": {"name": "mcp_call_tool", "description": "Bir MCP sunucusundaki belirli "
        "bir araci cagirir.",
        "parameters": {"type": "object", "properties": {"server_name": {"type": "string"},
        "tool_name": {"type": "string"}, "arguments": {"type": "object"}},
        "required": ["server_name", "tool_name"]}}},
]

AGENT_PERSONAS = {
    "arastirmaci": "Sen bir arastirma uzmanisin. Web'de arama yapar, kaynaklari karsilastirir, ozetlersin. "
                   "Sadece arastirma yap, kod yazma.",
    "kodlayici": "Sen uzman bir yazilimcisin. Dosya olusturur/duzenler, kod yazar, terminalde calistirir ve "
                 "test edersin. Once plan yap, sonra uygula.",
    "test_uzmani": "Sen bir test/QA uzmanisin. Kodu/sonucu inceler, hatalari ve eksikleri bulup raporlarsin.",
}

# MODEL ROUTER: basit sorular icin "fast_model", zor/kodlama/analiz icin "smart_model" kullanilir.
FAST_CHAIN = ["groq", "gemini", "cerebras", "openai", "mistral", "anthropic", "nvidia_nim",
              "openrouter", "github_models"]
SMART_CHAIN = ["anthropic", "openai", "gemini", "mistral", "nvidia_nim", "groq", "cerebras",
               "openrouter", "github_models"]
PROVIDER_INFO = {
    "openai": {"key_field": "openai_api_key", "base_url": None, "kind": "openai_compat",
               "fast_model": "gpt-4o-mini", "smart_model": "gpt-4o"},
    "anthropic": {"key_field": "anthropic_api_key", "base_url": None, "kind": "anthropic",
                  "fast_model": "claude-3-5-haiku-20241022", "smart_model": "claude-3-5-sonnet-20241022"},
    "gemini": {"key_field": "gemini_api_key", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "kind": "openai_compat", "fast_model": "gemini-2.0-flash", "smart_model": "gemini-2.0-flash"},
    "groq": {"key_field": "groq_api_key", "base_url": "https://api.groq.com/openai/v1", "kind": "openai_compat",
             "fast_model": "llama-3.1-8b-instant", "smart_model": "llama-3.3-70b-versatile"},
    "cerebras": {"key_field": "cerebras_api_key", "base_url": "https://api.cerebras.ai/v1", "kind": "openai_compat",
                 "fast_model": "llama3.1-8b", "smart_model": "llama-3.3-70b"},
    "mistral": {"key_field": "mistral_api_key", "base_url": "https://api.mistral.ai/v1", "kind": "openai_compat",
                "fast_model": "mistral-small-latest", "smart_model": "mistral-large-latest"},
    "nvidia_nim": {"key_field": "nvidia_nim_api_key", "base_url": "https://integrate.api.nvidia.com/v1",
                   "kind": "openai_compat", "fast_model": "meta/llama-3.1-8b-instruct",
                   "smart_model": "meta/llama-3.1-70b-instruct"},
    "openrouter": {"key_field": "openrouter_api_key", "base_url": "https://openrouter.ai/api/v1",
                   "kind": "openai_compat", "fast_model": "openai/gpt-4o-mini", "smart_model": "openai/gpt-4o"},
    "github_models": {"key_field": "github_models_token", "base_url": "https://models.inference.ai.azure.com",
                       "kind": "openai_compat", "fast_model": "gpt-4o-mini", "smart_model": "gpt-4o"},
    "ollama": {"key_field": None, "base_url": "http://localhost:11434/v1", "kind": "openai_compat",
               "fast_model": "qwen2.5:3b", "smart_model": "qwen2.5-coder:14b"},
}

_CODE_KEYWORDS = ("kod", "code", "python", "javascript", "typescript", "fonksiyon", "function", "hata", "bug",
                   "script", "dosya duzenle", "terminal", "compile", "class ", "def ", "npm", "pip install",
                   "algoritma", "mimari", "refactor", "debug", "test yaz", "api entegre", "sql")


def classify_task(user_text):
    """Basit heuristik: kodlama/analiz/uzun istekler 'smart', geri kalani 'fast' olarak siniflandirilir."""
    low = user_text.lower()
    if any(k in low for k in _CODE_KEYWORDS) or len(user_text) > 220:
        return "smart"
    return "fast"


def _oai_tools_to_anthropic(schemas):
    result = []
    for s in schemas:
        fn = s["function"]
        result.append({"name": fn["name"], "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}})})
    return result


ANTHROPIC_TOOLS = _oai_tools_to_anthropic(TOOL_SCHEMAS)

_TOOL_SCHEMA_BY_NAME = {s["function"]["name"]: s["function"] for s in TOOL_SCHEMAS}
_JSON_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def validate_tool_call(name, args):
    """Rejects an unknown tool name, a non-dict argument bag, a missing required
    field, or a field of the wrong JSON type -- BEFORE the tool runs. Every model
    (cloud or local) goes through this: a local model is more likely to hallucinate
    a bad call, but a cloud model can too, so the gate is unconditional, not
    provider-specific.
    """
    schema = _TOOL_SCHEMA_BY_NAME.get(name)
    if schema is None:
        return False, f"Bilinmeyen arac adi: '{name}'"
    if not isinstance(args, dict):
        return False, f"'{name}' icin argumanlar bir JSON nesnesi olmali, {type(args).__name__} geldi"
    params = schema.get("parameters", {})
    props = params.get("properties", {})
    for required_field in params.get("required", []):
        if required_field not in args:
            return False, f"'{name}' icin zorunlu alan eksik: '{required_field}'"
    for field_name, value in args.items():
        field_schema = props.get(field_name, {})
        expected_type = field_schema.get("type")
        checker = _JSON_TYPE_CHECKS.get(expected_type)
        if checker is not None and not checker(value):
            return False, f"'{name}.{field_name}' tipi '{expected_type}' olmali, gelen deger: {value!r}"
        allowed_values = field_schema.get("enum")
        if allowed_values is not None and value not in allowed_values:
            return False, f"'{name}.{field_name}' su degerlerden biri olmali: {allowed_values}, gelen: {value!r}"
    return True, None


class TouchpadOverlay(tk.Toplevel):
    """Ekranda serbestce gezdirilebilen, gercek fareyi kontrol eden sanal touchpad."""

    SENSITIVITY = 2.2

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.88)
        except Exception:
            pass
        self.geometry("220x180+120+120")
        self.configure(bg="#1e1e2e")

        handle = tk.Frame(self, bg="#313244", height=24)
        handle.pack(fill="x", side="top")
        tk.Label(handle, text="Arkana Yaslan Touchpad", bg="#313244", fg="#cdd6f4",
                 font=("Segoe UI", 8)).pack(side="left", padx=6)
        close_btn = tk.Label(handle, text="X", bg="#313244", fg="#f38ba8",
                              font=("Segoe UI", 10, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=8)
        close_btn.bind("<Button-1>", lambda e: self.destroy())

        handle.bind("<ButtonPress-1>", self._start_move_window)
        handle.bind("<B1-Motion>", self._do_move_window)

        pad = tk.Canvas(self, bg="#181825", highlightthickness=0)
        pad.pack(fill="both", expand=True, padx=4, pady=(2, 4))
        pad.create_text(110, 70, text="Fareyi hareket\nettirmek icin\nburayi surukleyin",
                         fill="#585b70", font=("Segoe UI", 9), justify="center")
        pad.bind("<ButtonPress-1>", self._start_drag)
        pad.bind("<B1-Motion>", self._do_drag)

        btns = tk.Frame(self, bg="#1e1e2e")
        btns.pack(fill="x", pady=(0, 6), padx=4)
        tk.Button(btns, text="Sol Tik", command=self._left_click, width=9).pack(side="left")
        tk.Button(btns, text="Sag Tik", command=self._right_click, width=9).pack(side="right")

        self._drag_last = None
        self._win_offset = (0, 0)

    def _start_move_window(self, event):
        self._win_offset = (event.x, event.y)

    def _do_move_window(self, event):
        x = self.winfo_pointerx() - self._win_offset[0]
        y = self.winfo_pointery() - self._win_offset[1]
        self.geometry(f"+{x}+{y}")

    def _start_drag(self, event):
        self._drag_last = (event.x, event.y)

    def _do_drag(self, event):
        if self._drag_last is None:
            self._drag_last = (event.x, event.y)
            return
        dx = (event.x - self._drag_last[0]) * self.SENSITIVITY
        dy = (event.y - self._drag_last[1]) * self.SENSITIVITY
        self._drag_last = (event.x, event.y)
        try:
            pyautogui.moveRel(dx, dy, duration=0)
        except pyautogui.FailSafeException:
            pass

    @staticmethod
    def _left_click():
        try:
            pyautogui.click()
        except pyautogui.FailSafeException:
            pass

    @staticmethod
    def _right_click():
        try:
            pyautogui.click(button="right")
        except pyautogui.FailSafeException:
            pass


class FloatingButton(tk.Toplevel):
    """Ekranda her zaman ustte duran, surukleyip tasiyabileceginiz Jarvis dugmesi.
    Tiklaninca SADECE kompakt sohbet penceresini acar - tam uygulama degil."""

    SIZE = 64

    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-transparentcolor", "#abcdef")
        except Exception:
            pass
        self.geometry(f"{self.SIZE}x{self.SIZE}+40+40")
        self.configure(bg="#abcdef")

        canvas = tk.Canvas(self, width=self.SIZE, height=self.SIZE, bg="#abcdef", highlightthickness=0)
        canvas.pack()
        canvas.create_oval(2, 2, self.SIZE - 2, self.SIZE - 2, fill="#1a1a2e", outline="#58a6ff", width=2)
        canvas.create_text(self.SIZE // 2, self.SIZE // 2, text="AY", fill="#58a6ff",
                            font=("Segoe UI", 14, "bold"))

        self._press_pos = None
        self._dragged = False
        canvas.bind("<ButtonPress-1>", self._on_press)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)

    def _on_press(self, event):
        self._press_pos = (event.x, event.y)
        self._dragged = False

    def _on_drag(self, event):
        self._dragged = True
        x = self.winfo_pointerx() - self._press_pos[0]
        y = self.winfo_pointery() - self._press_pos[1]
        self.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._dragged:
            btn_x = self.winfo_x()
            btn_y = self.winfo_y()
            self.master_app.open_compact_chat(near_x=btn_x, near_y=btn_y)


class JarvisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Arkana Yaslan - Kisisel AI Asistani")
        self.geometry("1000x740")
        self.minsize(780, 600)

        self.config_data = load_config()
        self.last_image_b64 = None
        self.last_photo = None
        self.chat_history = []

        self.live_watching = False
        self._live_thread = None
        self.touchpad = None
        self.floating_button = None
        self.compact_mode = False

        self.recording = False
        self._audio_frames = []
        self._audio_stream = None
        self.tts_enabled = True
        self._qdrant_client = None
        self._undo_stack = []
        self._subagent_depth = 0

        self._build_ui()
        self._refresh_status()
        self.floating_button = FloatingButton(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self._load_chat_history()
        self._restore_chat_view()
        self._log_system("Arkana Yaslan hazir. Ekranda gezdirebileceginiz yuvarlak dugmeyi kullanarak "
                          "beni her yerden acabilirsiniz. Sohbet kutusuna ne yapmami istediginizi yazin "
                          "veya mikrofon butonuna basip konusun.")
        # Uygulama acilir acilmaz ekrani otomatik izlemeye basla
        self._toggle_live()
        # Baslangicta kompakt (sadece chat) gorunumde ac
        self.after(300, lambda: self.open_compact_chat())

    def _on_close_request(self):
        """Pencereyi kapatmak yerine gizler - Jarvis arka planda, yuzen dugmede aktif kalir.
        (Not: uygulama sadece siz calistirdiginizda aktiftir, Windows acilisinda otomatik baslamaz.)"""
        self.withdraw()

    # ---------- UI ----------
    def _build_ui(self):
        self.top_frame = ttk.Frame(self, padding=10)
        self.top_frame.pack(fill="x")
        ttk.Label(self.top_frame, text="Arkana Yaslan", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.status_var = tk.StringVar(value="Durum kontrol ediliyor...")
        ttk.Label(self.top_frame, textvariable=self.status_var, foreground="#555").pack(side="right")

        self.btns_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.btns_frame.pack(fill="x")
        btns = self.btns_frame
        ttk.Button(btns, text="Durumu Yenile", command=self._refresh_status).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Ekrani Yakala", command=self._capture_screen_async).pack(side="left", padx=6)
        self.live_btn = ttk.Button(btns, text="Canli Izlemeyi Durdur", command=self._toggle_live)
        self.live_btn.pack(side="left", padx=6)
        ttk.Button(btns, text="Touchpad Goster", command=self._toggle_touchpad).pack(side="left", padx=6)
        ttk.Button(btns, text="Hafiza", command=self._open_memory_viewer).pack(side="left", padx=6)
        ttk.Button(btns, text="Geri Al", command=self._undo_last_action).pack(side="left", padx=6)
        ttk.Button(btns, text="Yeni Gorev", command=self._new_task).pack(side="left", padx=6)
        ttk.Button(btns, text="n8n Ac", command=lambda: webbrowser.open(N8N_URL)).pack(side="left", padx=6)
        self.tts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btns, text="Sesli Yanit", variable=self.tts_var,
                        command=lambda: setattr(self, "tts_enabled", self.tts_var.get())).pack(side="left", padx=6)
        ttk.Button(btns, text="Ayarlar", command=self._open_settings).pack(side="right")
        ttk.Button(btns, text="Baglantilari Test Et", command=self._test_connections_async).pack(side="right",
                                                                                                    padx=6)

        self.body = ttk.Panedwindow(self, orient="horizontal")
        self.body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.left_frame = ttk.Frame(self.body)
        self.image_label = ttk.Label(self.left_frame, text="Henuz ekran goruntusu yok.\n'Ekrani Yakala' "
                                      "butonuna basin.", anchor="center", justify="center")
        self.image_label.pack(fill="both", expand=True)
        self.body.add(self.left_frame, weight=3)

        self.right_frame = ttk.Frame(self.body)
        right = self.right_frame
        chat_header = ttk.Frame(right)
        chat_header.pack(fill="x")
        ttk.Label(chat_header, text="Arkana Yaslan Sohbet", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.expand_btn = ttk.Button(chat_header, text="Tam Gorunum", command=self._show_full_view)
        # Sadece kompakt moddayken gorunur, tam moddayken paketlenmez
        self.chat_box = scrolledtext.ScrolledText(right, wrap="word", height=10, state="disabled")
        self.chat_box.pack(fill="both", expand=True)
        self.chat_box.tag_config("user", foreground="#1a73e8")
        self.chat_box.tag_config("assistant", foreground="#188038")
        self.chat_box.tag_config("system", foreground="#888888")
        self.chat_box.tag_config("tool", foreground="#b8860b")

        entry_row = ttk.Frame(right)
        entry_row.pack(fill="x", pady=(6, 0))
        self.chat_entry = ttk.Entry(entry_row)
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())
        self.send_btn = ttk.Button(entry_row, text="Gonder", command=self._send_chat)
        self.send_btn.pack(side="left", padx=(6, 0))
        self.mic_btn = ttk.Button(entry_row, text="Mikrofon", command=self._toggle_recording)
        self.mic_btn.pack(side="left", padx=(6, 0))
        self.body.add(right, weight=2)

    # ---------- Kompakt (sadece chat) gorunum ----------
    def open_compact_chat(self, near_x=None, near_y=None):
        self.deiconify()
        self.lift()
        self.focus_force()
        if not self.compact_mode:
            self.compact_mode = True
            self.top_frame.pack_forget()
            self.btns_frame.pack_forget()
            try:
                self.body.forget(self.left_frame)
            except Exception:
                pass
            self.chat_header_expand_visible(True)
        w, h = 380, 480
        if near_x is not None:
            x = min(max(near_x + 70, 0), self.winfo_screenwidth() - w)
            y = min(max(near_y, 0), self.winfo_screenheight() - h)
            self.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.geometry(f"{w}x{h}")

    def chat_header_expand_visible(self, visible):
        if visible:
            self.expand_btn.pack(side="right")
        else:
            self.expand_btn.pack_forget()

    def _show_full_view(self):
        self.compact_mode = False
        self.top_frame.pack(fill="x")
        self.btns_frame.pack(fill="x")
        try:
            self.body.insert(0, self.left_frame, weight=3)
        except Exception:
            pass
        self.chat_header_expand_visible(False)
        self.geometry("1000x740")

    def _append_chat(self, who, text, tag):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{who}: ", (tag,))
        self.chat_box.insert("end", text + "\n\n")
        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")

    def _log_system(self, text):
        self.after(0, lambda: self._append_chat("Sistem", text, "system"))

    def _log_tool(self, text):
        self.after(0, lambda: self._append_chat("Arac", text, "tool"))

    # ---------- Status ----------
    def _refresh_status(self):
        def check():
            n8n_ok = self._ping(f"{N8N_URL}/healthz")
            router_ok = self._ping(f"{HYPER_ROUTER_URL}/health")
            self.status_var.set(
                f"{'n8n: calisiyor' if n8n_ok else 'n8n: kapali'}  |  "
                f"{'Ekran Servisi: calisiyor' if router_ok else 'Ekran Servisi: kapali'}"
            )
        threading.Thread(target=check, daemon=True).start()

    @staticmethod
    def _ping(url):
        try:
            return requests.get(url, timeout=3).status_code == 200
        except Exception:
            return False

    # ---------- Screen capture ----------
    def _capture_screen_async(self):
        threading.Thread(target=self._capture_screen, daemon=True).start()

    def _capture_screen(self):
        try:
            r = requests.post(f"{HYPER_ROUTER_URL}/v1/tools/screen_capture", timeout=15)
            data = r.json()
            if not data.get("ok"):
                self._log_system(f"HATA: {data.get('error', 'bilinmeyen hata')}")
                return
            self.last_image_b64 = data["image_base64"]
            self.after(0, self._show_captured_image)
        except Exception as e:
            self._log_system(f"HATA: Ekran servisine ulasilamadi ({e})")

    def _show_captured_image(self):
        try:
            raw = base64.b64decode(self.last_image_b64)
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((640, 480))
            self.last_photo = ImageTk.PhotoImage(img)
            self.image_label.configure(image=self.last_photo, text="")
        except Exception as e:
            self._log_system(f"Goruntu gosterilemedi: {e}")

    def _toggle_live(self):
        if self.live_watching:
            self.live_watching = False
            self.live_btn.configure(text="Canli Izlemeyi Baslat")
            self._log_system("Canli izleme durduruldu.")
        else:
            self.live_watching = True
            self.live_btn.configure(text="Canli Izlemeyi Durdur")
            self._log_system(f"Canli izleme baslatildi ({LIVE_INTERVAL_SEC} sn) - ekraninizi surekli goruyorum.")
            self._live_thread = threading.Thread(target=self._live_loop, daemon=True)
            self._live_thread.start()

    def _live_loop(self):
        while self.live_watching:
            self._capture_screen()
            time.sleep(LIVE_INTERVAL_SEC)

    # ---------- Touchpad ----------
    def _toggle_touchpad(self):
        if self.touchpad is not None and self.touchpad.winfo_exists():
            self.touchpad.destroy()
            self.touchpad = None
        else:
            self.touchpad = TouchpadOverlay(self)

    # ---------- Active window awareness ----------
    @staticmethod
    def _get_active_window_title():
        if gw is None:
            return None
        try:
            win = gw.getActiveWindow()
            return win.title if win else None
        except Exception:
            return None

    # ---------- Kalici Hafiza (Qdrant, yerel) ----------
    MEMORY_COLLECTION = "memory"

    def _embed_text(self, text):
        resp = requests.post("http://localhost:11434/api/embeddings",
                              json={"model": "nomic-embed-text", "prompt": text}, timeout=30)
        resp.raise_for_status()
        return resp.json()["embedding"]

    def _qdrant(self):
        if getattr(self, "_qdrant_client", None) is None:
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance
            db_path = str(CONFIG_DIR / "qdrant_db")
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._qdrant_client = QdrantClient(path=db_path)
            existing = [c.name for c in self._qdrant_client.get_collections().collections]
            if self.MEMORY_COLLECTION not in existing:
                self._qdrant_client.create_collection(
                    collection_name=self.MEMORY_COLLECTION,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
        return self._qdrant_client

    def _memory_save(self, text, tag=""):
        from qdrant_client.models import PointStruct
        client = self._qdrant()
        vec = self._embed_text(text)
        client.upsert(collection_name=self.MEMORY_COLLECTION, points=[
            PointStruct(id=str(uuid.uuid4()), vector=vec,
                        payload={"text": text, "tag": tag, "ts": time.time()})
        ])

    def _memory_search(self, query, limit=5):
        client = self._qdrant()
        vec = self._embed_text(query)
        hits = client.query_points(collection_name=self.MEMORY_COLLECTION, query=vec, limit=limit).points
        return [{"text": h.payload.get("text"), "tag": h.payload.get("tag"), "score": round(h.score, 3)}
                for h in hits]

    def _memory_list_all(self):
        client = self._qdrant()
        points, _ = client.scroll(collection_name=self.MEMORY_COLLECTION, limit=500)
        return sorted(points, key=lambda p: p.payload.get("ts", 0), reverse=True)

    def _memory_delete(self, point_id):
        client = self._qdrant()
        client.delete(collection_name=self.MEMORY_COLLECTION, points_selector=[point_id])

    def _open_memory_viewer(self):
        win = tk.Toplevel(self)
        win.title("Hafiza")
        win.geometry("560x420")
        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for w in container.winfo_children():
                w.destroy()
            try:
                points = self._memory_list_all()
            except Exception as e:
                ttk.Label(container, text=f"Hafiza okunamadi: {e}").pack()
                return
            if not points:
                ttk.Label(container, text="Kayitli hafiza yok.").pack()
                return
            canvas = tk.Canvas(container, highlightthickness=0)
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas)
            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            for p in points:
                row = ttk.Frame(inner)
                row.pack(fill="x", pady=2)
                tag = p.payload.get("tag") or "-"
                ttk.Label(row, text=f"[{tag}] {p.payload.get('text', '')}", wraplength=420,
                          justify="left").pack(side="left", fill="x", expand=True)
                ttk.Button(row, text="Sil", width=6,
                           command=lambda pid=p.id: (self._memory_delete(pid), refresh())).pack(side="right")

        refresh()

    # ---------- Voice: mic (STT) ----------
    def _toggle_recording(self):
        if sd is None or sf is None:
            messagebox.showwarning("Mikrofon yok", "Ses kaydi kutuphaneleri kurulamadi.")
            return
        if not self.recording:
            self.recording = True
            self._audio_frames = []
            self.mic_btn.configure(text="Durdur (Kayit)")
            self._audio_stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                                                 callback=self._on_audio_block)
            self._audio_stream.start()
            self._log_system("Dinliyorum... bitirince tekrar 'Durdur' butonuna basin.")
        else:
            self.recording = False
            self.mic_btn.configure(text="Mikrofon")
            self._audio_stream.stop()
            self._audio_stream.close()
            threading.Thread(target=self._transcribe_recording, daemon=True).start()

    def _on_audio_block(self, indata, frames, time_info, status):
        self._audio_frames.append(indata.copy())

    def _transcribe_recording(self):
        try:
            import numpy as np
            if not self._audio_frames:
                self._log_system("Ses kaydedilmedi.")
                return
            audio = np.concatenate(self._audio_frames, axis=0)
            wav_path = CONFIG_DIR / "last_recording.wav"
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            sf.write(str(wav_path), audio, 16000)

            api_key = self.config_data.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self._log_system("Metne cevirmek icin once bir OpenAI API anahtari girin.")
                return
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            with open(wav_path, "rb") as f:
                result = client.audio.transcriptions.create(model="whisper-1", file=f)
            text = result.text.strip()
            if text:
                self.after(0, lambda: (self.chat_entry.delete(0, "end"), self.chat_entry.insert(0, text),
                                        self._send_chat()))
        except Exception as e:
            self._log_system(f"Ses metne cevrilemedi: {e}")

    # ---------- Voice: speak (TTS) ----------
    def _speak(self, text):
        if not self.tts_enabled or not text:
            return

        def run():
            openai_key = self.config_data.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            if openai_key and sd is not None and sf is not None:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    resp = client.audio.speech.create(model="tts-1", voice="alloy", input=text,
                                                        response_format="wav")
                    wav_path = CONFIG_DIR / "last_reply.wav"
                    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                    resp.write_to_file(str(wav_path))
                    data, samplerate = sf.read(str(wav_path), dtype="float32")
                    sd.play(data, samplerate)
                    sd.wait()
                    return
                except Exception as e:
                    self._log_system(f"OpenAI sesli yanit basarisiz ({e}), yerel sese geciliyor...")
            if pyttsx3 is not None:
                try:
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _build_system_prompt(self, active_window, user_text):
        base = (
            "Sen 'Arkana Yaslan' adinda bir kisisel bilgisayar asistanisin. Kullanicinin ekranini "
            "gorebilir, gercek araclari (tiklama, dosya islemleri, komut calistirma, e-posta vb.) "
            "cagirarak onun bilgisayarinda gercekten islem yapabilirsin. Guvenlik icin bazi araclar "
            "kullanicidan onay ister; onaylanmazsa alternatif bir yol oner. Her zaman Turkce cevap ver, "
            "yaptigin islemleri kisaca ozetle."
        )
        if active_window:
            base += f"\n\nKullanicinin su an aktif penceresi: '{active_window}'."
        try:
            memories = self._memory_search(user_text, limit=4)
            memories = [m for m in memories if m["score"] > 0.5]
            if memories:
                recall = "\n".join(f"- [{m['tag'] or 'genel'}] {m['text']}" for m in memories)
                base += f"\n\nGecmis hafizadan ilgili bilgiler (dogrulugundan emin degilsen kullaniciya sor):\n{recall}"
        except Exception:
            pass
        return base

    # ---------- Coklu Ajan (alt-ajana gorev devretme) ----------
    def _run_subagent(self, role, task, max_turns=6):
        if self._subagent_depth >= 2:
            return {"ok": False, "error": "Alt-ajan derinligi asildi, daha fazla devredilemez."}
        from openai import OpenAI

        self._subagent_depth += 1
        try:
            system_prompt = AGENT_PERSONAS.get(role, "Sen yardimci bir alt-ajansin.")
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": task}]
            providers = [p for p in self._available_providers("smart") if p["kind"] == "openai_compat"]

            client, model = None, None
            resp = None
            for p in providers:
                try:
                    candidate = OpenAI(api_key=p["api_key"], base_url=p["base_url"])
                    resp = candidate.chat.completions.create(model=p["model"], messages=messages,
                                                              tools=TOOL_SCHEMAS, max_tokens=800)
                    client, model = candidate, p["model"]
                    break
                except Exception:
                    continue
            if client is None:
                return {"ok": False, "error": "Alt-ajan icin hicbir saglayiciya ulasilamadi."}

            for _ in range(max_turns):
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    return {"ok": True, "role": role, "result": msg.content or "(bos yanit)"}
                messages.append({"role": "assistant", "content": msg.content,
                                  "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    try:
                        targs = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        targs = {}
                    result = self._execute_tool(tc.function.name, targs)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)[:4000]})
                resp = client.chat.completions.create(model=model, messages=messages, tools=TOOL_SCHEMAS,
                                                       max_tokens=800)
            return {"ok": True, "role": role, "result": "(cok fazla adim, kesildi)"}
        finally:
            self._subagent_depth -= 1

    # ---------- MCP Client ----------
    def _get_mcp_servers(self):
        raw = self.config_data.get("mcp_servers_json", "")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _mcp_list_tools(self, server_name):
        servers = self._get_mcp_servers()
        if server_name not in servers:
            return {"ok": False, "error": f"'{server_name}' Ayarlar'da tanimli degil."}
        cfg = servers[server_name]
        try:
            import asyncio
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client

            async def _run():
                params = StdioServerParameters(command=cfg["command"], args=cfg.get("args", []))
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.list_tools()
                        return [{"name": t.name, "description": t.description} for t in result.tools]

            return {"ok": True, "tools": asyncio.run(_run())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _mcp_call_tool(self, server_name, tool_name, arguments):
        servers = self._get_mcp_servers()
        if server_name not in servers:
            return {"ok": False, "error": f"'{server_name}' Ayarlar'da tanimli degil."}
        cfg = servers[server_name]
        try:
            import asyncio
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client

            async def _run():
                params = StdioServerParameters(command=cfg["command"], args=cfg.get("args", []))
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments or {})
                        return [getattr(c, "text", str(c)) for c in result.content]

            return {"ok": True, "content": asyncio.run(_run())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- Gorev devamliligi ----------
    CHAT_HISTORY_FILE = CONFIG_DIR / "chat_history.json"

    def _save_chat_history(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.CHAT_HISTORY_FILE.write_text(json.dumps(self.chat_history[-40:], ensure_ascii=False),
                                                encoding="utf-8")
        except Exception:
            pass

    def _load_chat_history(self):
        if self.CHAT_HISTORY_FILE.exists():
            try:
                self.chat_history = json.loads(self.CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.chat_history = []

    def _restore_chat_view(self):
        if not self.chat_history:
            return
        self._log_system(f"Onceki oturumdan {len(self.chat_history)} mesaj geri yuklendi, kaldiginiz yerden "
                          "devam edebilirsiniz.")
        for m in self.chat_history:
            content = m["content"]
            if isinstance(content, list):
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("text"))
            who = "Siz" if m["role"] == "user" else "Arkana Yaslan"
            tag = "user" if m["role"] == "user" else "assistant"
            self._append_chat(who, content, tag)

    def _new_task(self):
        if messagebox.askyesno("Yeni Gorev", "Mevcut sohbet gecmisi silinip yeni bir gorevle mi baslansin?"):
            self.chat_history = []
            self._save_chat_history()
            self.chat_box.configure(state="normal")
            self.chat_box.delete("1.0", "end")
            self.chat_box.configure(state="disabled")
            self._log_system("Yeni gorev basladi.")

    # ---------- Geri Al ----------
    def _undo_last_action(self):
        if not self._undo_stack:
            messagebox.showinfo("Geri Al", "Geri alinacak bir islem yok.")
            return
        action = self._undo_stack.pop()
        try:
            if action["action"] == "write_file":
                path = Path(action["path"])
                if action["previous"] is None:
                    path.unlink(missing_ok=True)
                    msg = f"'{path}' silindi (yeni olusturulmustu)."
                else:
                    path.write_text(action["previous"], encoding="utf-8")
                    msg = f"'{path}' onceki haline geri alindi."
            elif action["action"] == "delete_file":
                src = Path(action["trash_path"])
                dst = Path(action["path"])
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                msg = f"'{dst}' geri yuklendi."
            else:
                msg = "Bilinmeyen islem, geri alinamadi."
            self._log_system(f"Geri alindi: {msg}")
            messagebox.showinfo("Geri Al", msg)
        except Exception as e:
            messagebox.showerror("Geri Al Hatasi", str(e))

    # ---------- Settings ----------
    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("Ayarlar")
        win.geometry("560x760")
        win.resizable(False, False)

        fields = [
            ("openai_api_key", "OpenAI API Anahtari (1. tercih)", True),
            ("anthropic_api_key", "Anthropic (Claude) API Anahtari (2. tercih)", True),
            ("gemini_api_key", "Google Gemini API Anahtari (3. tercih)", True),
            ("groq_api_key", "Groq API Anahtari (4. tercih)", True),
            ("cerebras_api_key", "Cerebras API Anahtari (5. tercih)", True),
            ("mistral_api_key", "Mistral API Anahtari (6. tercih)", True),
            ("nvidia_nim_api_key", "NVIDIA NIM API Anahtari (7. tercih)", True),
            ("openrouter_api_key", "OpenRouter API Anahtari (8. tercih, yedek)", True),
            ("github_models_token", "GitHub Models Token (9. tercih, yedek)", True),
            ("smtp_host", "SMTP Sunucu (orn: smtp.gmail.com)", False),
            ("smtp_port", "SMTP Port (orn: 587)", False),
            ("smtp_user", "E-posta adresiniz", False),
            ("smtp_password", "E-posta uygulama sifresi", True),
            ("mcp_servers_json", 'MCP Sunuculari (JSON, ileri seviye - orn: {"fs":{"command":"npx",'
             '"args":["-y","@modelcontextprotocol/server-filesystem","C:\\\\Users\\\\muslu"]}})', False),
        ]
        entries = {}
        for i, (key, label, secret) in enumerate(fields):
            ttk.Label(win, text=label, wraplength=220, justify="left").grid(row=i, column=0, sticky="w",
                                                                              padx=10, pady=6)
            e = ttk.Entry(win, show="*" if secret else "", width=28)
            e.insert(0, str(self.config_data.get(key, "")))
            e.grid(row=i, column=1, padx=10, pady=6)
            entries[key] = e

        def save():
            for key, e in entries.items():
                val = e.get().strip()
                if val:
                    self.config_data[key] = val
            save_config(self.config_data)
            messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi.")
            win.destroy()

        ttk.Button(win, text="Kaydet", command=save).grid(row=len(fields), column=0, columnspan=2, pady=14)

    # ---------- Confirmation (main-thread safe) ----------
    def _confirm(self, title, message):
        result = {}
        event = threading.Event()

        def show():
            result["ok"] = messagebox.askyesno(title, message, icon="warning")
            event.set()

        self.after(0, show)
        event.wait()
        return result.get("ok", False)

    # ---------- Tool execution ----------
    def _execute_tool(self, name, args):
        valid, err = validate_tool_call(name, args)
        if not valid:
            self._log_tool(f"REDDEDILDI ({name}): {err}")
            return {"ok": False, "error": f"Arac cagrisi reddedildi (schema): {err}"}
        try:
            if name in CONFIRM_REQUIRED:
                desc = {
                    "run_command": f"Su komutu calistirmak istiyorum:\n\n{args.get('command')}\n\nOnayliyor musunuz?",
                    "git_push": f"'{args.get('repo_path')}' deposundaki commit'leri uzak sunucuya gondermek "
                                 f"istiyorum. Onayliyor musunuz?",
                    "send_email": f"Su e-postayi gondermek istiyorum:\nKime: {args.get('to')}\n"
                                   f"Konu: {args.get('subject')}\n\nOnayliyor musunuz?",
                }.get(name, f"'{name}' islemini yapmak istiyorum. Onayliyor musunuz?")
                if not self._confirm("Onay Gerekli", desc):
                    return {"ok": False, "error": "Kullanici onaylamadi."}

            if name == "write_file":
                path = Path(args["path"]).expanduser()
                old_content = None
                if path.exists():
                    old_content = path.read_text(encoding="utf-8", errors="replace")
                    diff = "\n".join(difflib.unified_diff(
                        old_content.splitlines(), args["content"].splitlines(),
                        fromfile=str(path), tofile=str(path), lineterm=""))
                    if not self._confirm("Onay Gerekli - Degisiklik", f"'{path}' guncellenecek:\n\n{diff[:2500]}"):
                        return {"ok": False, "error": "Kullanici onaylamadi."}
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(args["content"], encoding="utf-8")
                self._undo_stack.append({"action": "write_file", "path": str(path), "previous": old_content})
                self._log_tool(f"write_file -> {path} (Geri Al ile eski haline donebilirsiniz)")
                return {"ok": True, "path": str(path)}

            if name == "delete_file":
                path = Path(args["path"]).expanduser()
                if not self._confirm("Onay Gerekli", f"'{path}' silinsin mi? (Geri Al ile kurtarabilirsiniz)"):
                    return {"ok": False, "error": "Kullanici onaylamadi."}
                trash_path = CONFIG_DIR / "trash" / f"{uuid.uuid4()}_{path.name}"
                trash_path.parent.mkdir(parents=True, exist_ok=True)
                if path.is_dir():
                    shutil.copytree(path, trash_path)
                    shutil.rmtree(path)
                else:
                    shutil.copy2(path, trash_path)
                    path.unlink()
                self._undo_stack.append({"action": "delete_file", "path": str(path), "trash_path": str(trash_path)})
                self._log_tool(f"delete_file -> {path} (Geri Al ile kurtarabilirsiniz)")
                return {"ok": True}

            if name == "read_file":
                path = Path(args["path"]).expanduser()
                content = path.read_text(encoding="utf-8", errors="replace")
                self._log_tool(f"read_file -> {path} ({len(content)} karakter)")
                return {"ok": True, "content": content[:20000]}

            if name == "list_dir":
                path = Path(args["path"]).expanduser()
                items = [p.name + ("/" if p.is_dir() else "") for p in sorted(path.iterdir())]
                self._log_tool(f"list_dir -> {path} ({len(items)} oge)")
                return {"ok": True, "items": items[:300]}

            if name == "search_files":
                path = Path(args["path"]).expanduser()
                matches = [str(p) for p in path.rglob(args["pattern"])][:200]
                self._log_tool(f"search_files -> {path} / {args['pattern']} ({len(matches)} sonuc)")
                return {"ok": True, "matches": matches}

            if name == "run_command":
                self._log_tool(f"run_command -> {args['command']}")
                proc = subprocess.run(args["command"], shell=True, capture_output=True, text=True, timeout=60)
                return {"ok": proc.returncode == 0, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:],
                        "returncode": proc.returncode}

            if name == "git_status":
                proc = subprocess.run(["git", "status"], cwd=args["repo_path"], capture_output=True, text=True)
                self._log_tool(f"git_status -> {args['repo_path']}")
                return {"ok": True, "output": proc.stdout + proc.stderr}

            if name == "git_commit":
                subprocess.run(["git", "add", "-A"], cwd=args["repo_path"], capture_output=True, text=True)
                proc = subprocess.run(["git", "commit", "-m", args["message"]], cwd=args["repo_path"],
                                       capture_output=True, text=True)
                self._log_tool(f"git_commit -> {args['repo_path']}: {args['message']}")
                return {"ok": proc.returncode == 0, "output": proc.stdout + proc.stderr}

            if name == "git_push":
                proc = subprocess.run(["git", "push"], cwd=args["repo_path"], capture_output=True, text=True,
                                       timeout=60)
                self._log_tool(f"git_push -> {args['repo_path']}")
                return {"ok": proc.returncode == 0, "output": proc.stdout + proc.stderr}

            if name == "click":
                pyautogui.click(args["x"], args["y"], button=args.get("button", "left"))
                self._log_tool(f"click -> ({args['x']}, {args['y']})")
                return {"ok": True}

            if name == "type_text":
                pyautogui.write(args["text"])
                self._log_tool(f"type_text -> {args['text'][:60]}")
                return {"ok": True}

            if name == "hotkey":
                pyautogui.hotkey(*args["keys"])
                self._log_tool(f"hotkey -> {'+'.join(args['keys'])}")
                return {"ok": True}

            if name == "scroll":
                pyautogui.scroll(args["clicks"])
                self._log_tool(f"scroll -> {args['clicks']}")
                return {"ok": True}

            if name == "open_url":
                webbrowser.open(args["url"])
                self._log_tool(f"open_url -> {args['url']}")
                return {"ok": True}

            if name == "open_app":
                os.startfile(args["name"])
                self._log_tool(f"open_app -> {args['name']}")
                return {"ok": True}

            if name == "get_clipboard":
                return {"ok": True, "text": pyperclip.paste()}

            if name == "set_clipboard":
                pyperclip.copy(args["text"])
                self._log_tool("set_clipboard")
                return {"ok": True}

            if name == "ocr_screen":
                try:
                    import pytesseract
                    user_tessdata = Path.home() / ".omniai" / "tessdata"
                    config = f'--tessdata-dir "{user_tessdata}"' if user_tessdata.exists() else ""
                    text = pytesseract.image_to_string(pyautogui.screenshot(), lang="tur+eng", config=config)
                    self._log_tool(f"ocr_screen -> {len(text)} karakter okundu")
                    return {"ok": True, "text": text}
                except Exception as e:
                    return {"ok": False, "error": f"OCR kullanilamiyor: {e}"}

            if name == "send_email":
                import smtplib
                from email.mime.text import MIMEText
                cfg = self.config_data
                if not all(cfg.get(k) for k in ("smtp_host", "smtp_port", "smtp_user", "smtp_password")):
                    return {"ok": False, "error": "E-posta ayarlari eksik. Once Ayarlar'dan SMTP bilgilerini girin."}
                msg = MIMEText(args["body"])
                msg["Subject"] = args["subject"]
                msg["From"] = cfg["smtp_user"]
                msg["To"] = args["to"]
                with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"])) as server:
                    server.starttls()
                    server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.send_message(msg)
                self._log_tool(f"send_email -> {args['to']}")
                return {"ok": True}

            if name == "read_document":
                try:
                    from docling.document_converter import DocumentConverter
                except ImportError:
                    return {"ok": False, "error": "Docling henuz kurulmadi/kurulum devam ediyor."}
                self._log_tool(f"read_document -> {args['path']}")
                result = DocumentConverter().convert(args["path"])
                text = result.document.export_to_markdown()
                return {"ok": True, "content": text[:20000]}

            if name == "web_search":
                try:
                    import asyncio
                    from crawl4ai import AsyncWebCrawler
                except ImportError:
                    return {"ok": False, "error": "Crawl4AI henuz kurulmadi/kurulum devam ediyor."}
                self._log_tool(f"web_search -> {args['url']}")

                async def _crawl():
                    async with AsyncWebCrawler() as crawler:
                        r = await crawler.arun(url=args["url"])
                        return r.markdown

                content = asyncio.run(_crawl())
                return {"ok": True, "content": str(content)[:20000]}

            if name == "get_active_window":
                title = self._get_active_window_title()
                return {"ok": True, "active_window": title or "(bilinmiyor)"}

            if name == "memory_save":
                self._memory_save(args["text"], args.get("tag", ""))
                self._log_tool(f"memory_save -> {args['text'][:60]}")
                return {"ok": True}

            if name == "memory_search":
                results = self._memory_search(args["query"])
                self._log_tool(f"memory_search -> {args['query'][:60]} ({len(results)} sonuc)")
                return {"ok": True, "results": results}

            if name == "delegate_to_agent":
                self._log_tool(f"delegate_to_agent -> {args['role']}: {args['task'][:60]}")
                return self._run_subagent(args["role"], args["task"])

            if name == "mcp_list_tools":
                self._log_tool(f"mcp_list_tools -> {args['server_name']}")
                return self._mcp_list_tools(args["server_name"])

            if name == "mcp_call_tool":
                self._log_tool(f"mcp_call_tool -> {args['server_name']}.{args['tool_name']}")
                return self._mcp_call_tool(args["server_name"], args["tool_name"], args.get("arguments", {}))

            return {"ok": False, "error": f"Bilinmeyen arac: {name}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- Baglanti Testi ----------
    def _test_connections_async(self):
        threading.Thread(target=self._test_connections, daemon=True).start()

    def _test_connections(self):
        from openai import OpenAI
        self._log_system("Baglantilar test ediliyor...")
        for name in list(dict.fromkeys(FAST_CHAIN + SMART_CHAIN)):
            info = PROVIDER_INFO[name]
            key = self.config_data.get(info["key_field"]) or os.environ.get(info["key_field"].upper())
            if not key:
                self._log_system(f"  - {name}: anahtar girilmemis (atlandi)")
                continue
            try:
                if info["kind"] == "anthropic":
                    import anthropic
                    client = anthropic.Anthropic(api_key=key)
                    client.messages.create(model=info["fast_model"], max_tokens=5,
                                            messages=[{"role": "user", "content": "hi"}])
                else:
                    client = OpenAI(api_key=key, base_url=info["base_url"])
                    client.chat.completions.create(model=info["fast_model"],
                                                    messages=[{"role": "user", "content": "hi"}], max_tokens=5)
                self._log_system(f"  OK {name}: CALISIYOR")
            except Exception as e:
                self._log_system(f"  HATA {name}: ({str(e)[:120]})")
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            self._log_system("  OK ollama: CALISIYOR (yerel)" if r.status_code == 200
                              else "  HATA ollama: yanit vermedi")
        except Exception as e:
            self._log_system(f"  HATA ollama: ({e})")
        self._log_system("Test tamamlandi.")

    # ---------- Chat / AI (function calling) ----------
    def _send_chat(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")
        self._append_chat("Siz", text, "user")

        tier = classify_task(text)
        providers = self._available_providers(tier)
        if not any(self.config_data.get(PROVIDER_INFO[p["name"]]["key_field"]) for p in providers
                   if p["name"] != "ollama") and not self._ping("http://localhost:11434/api/tags"):
            self._append_chat("Arkana Yaslan", "Once 'Ayarlar' butonundan en az bir API anahtari girin "
                                                "(veya Ollama'nin calistigindan emin olun).", "assistant")
            return

        if not self.last_image_b64:
            self._capture_screen()

        self._log_system(f"(model router: '{tier}' -> {providers[0]['name']}/{providers[0]['model']})")
        self.send_btn.state(["disabled"])
        threading.Thread(target=self._agent_loop, args=(text, tier), daemon=True).start()

    def _available_providers(self, tier="fast"):
        chain = SMART_CHAIN if tier == "smart" else FAST_CHAIN
        result = []
        for name in chain:
            info = PROVIDER_INFO[name]
            key = self.config_data.get(info["key_field"]) or os.environ.get(info["key_field"].upper())
            if key:
                result.append({"name": name, "api_key": key, "model": info[f"{tier}_model"], **info})
        # Ollama: son care olarak her zaman denenir (anahtar gerekmez, calismiyorsa zaten baglanti hatasi verir)
        ollama_info = PROVIDER_INFO["ollama"]
        result.append({"name": "ollama", "api_key": "ollama", "model": ollama_info[f"{tier}_model"],
                        **ollama_info})
        return result

    def _run_anthropic(self, provider, user_text, active_window):
        """Anthropic (Claude) native mesaj/arac formatiyla calisir. Basarili olursa True doner
        (yanit gosterilmis, sohbet gecmisine eklenmis olur), ilk cagri basarisiz olursa False
        doner (fallback zinciri siradaki saglayiciya gecer)."""
        import anthropic

        system_prompt = self._build_system_prompt(active_window, user_text)

        content = [{"type": "text", "text": user_text}]
        if self.last_image_b64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                          "data": self.last_image_b64}})

        messages = list(self.chat_history[-10:])
        messages.append({"role": "user", "content": content})

        client = anthropic.Anthropic(api_key=provider["api_key"])
        try:
            resp = client.messages.create(model=provider["model"], max_tokens=800, system=system_prompt,
                                           messages=messages, tools=ANTHROPIC_TOOLS)
        except Exception as e:
            self._log_system(f"anthropic kullanilamadi ({e}), siradaki saglayiciya geciliyor...")
            return False

        self._log_system("(anthropic saglayicisi kullaniliyor)")
        try:
            for _ in range(6):
                tool_blocks = [b for b in resp.content if b.type == "tool_use"]
                if not tool_blocks:
                    text = "".join(b.text for b in resp.content if b.type == "text") or "(bos yanit)"
                    self.chat_history.append({"role": "user", "content": user_text})
                    self.chat_history.append({"role": "assistant", "content": text})
                    self._save_chat_history()
                    self.after(0, lambda: self._append_chat("Arkana Yaslan", text, "assistant"))
                    self._speak(text)
                    return True

                messages.append({"role": "assistant", "content": resp.content})
                tool_results = []
                for tb in tool_blocks:
                    result = self._execute_tool(tb.name, tb.input or {})
                    tool_results.append({"type": "tool_result", "tool_use_id": tb.id,
                                          "content": json.dumps(result)[:4000]})
                messages.append({"role": "user", "content": tool_results})

                resp = client.messages.create(model=provider["model"], max_tokens=800, system=system_prompt,
                                               messages=messages, tools=ANTHROPIC_TOOLS)

            self.after(0, lambda: self._append_chat("Arkana Yaslan", "Cok fazla arac adimi oldu, durduruyorum.",
                                                      "assistant"))
            return True
        except Exception as e:
            self.after(0, lambda: self._append_chat("Arkana Yaslan", f"Hata olustu: {e}", "assistant"))
            return True

    def _agent_loop(self, user_text, tier):
        from openai import OpenAI

        providers = self._available_providers(tier)
        if not providers:
            self.after(0, lambda: self._append_chat(
                "Arkana Yaslan", "Hicbir API anahtari girilmemis.", "assistant"))
            self.after(0, lambda: self.send_btn.state(["!disabled"]))
            return

        content = [{"type": "text", "text": user_text}]
        if self.last_image_b64:
            content.append({"type": "image_url",
                             "image_url": {"url": f"data:image/jpeg;base64,{self.last_image_b64}"}})

        active_window = self._get_active_window_title()
        messages = [{"role": "system", "content": self._build_system_prompt(active_window, user_text)}]
        messages.extend(self.chat_history[-10:])
        messages.append({"role": "user", "content": content})

        client, model, active_name, resp = None, None, None, None
        last_error = None
        for p in providers:
            try:
                if p["kind"] == "anthropic":
                    handled = self._run_anthropic(p, user_text, active_window)
                    if handled:
                        self.after(0, lambda: self.send_btn.state(["!disabled"]))
                        return
                    continue
                candidate = OpenAI(api_key=p["api_key"], base_url=p["base_url"])
                resp = candidate.chat.completions.create(
                    model=p["model"], messages=messages, tools=TOOL_SCHEMAS, max_tokens=800,
                )
                client, model, active_name = candidate, p["model"], p["name"]
                break
            except Exception as e:
                last_error = e
                self._log_system(f"{p['name']} kullanilamadi ({e}), siradaki saglayiciya geciliyor...")
                continue

        if client is None:
            self.after(0, lambda: self._append_chat(
                "Arkana Yaslan", f"Hicbir saglayiciya ulasilamadi. Son hata: {last_error}", "assistant"))
            self.after(0, lambda: self.send_btn.state(["!disabled"]))
            return

        if active_name != "openai":
            self._log_system(f"({active_name} saglayicisi kullaniliyor)")

        try:
            for _ in range(6):  # en fazla 6 arac-cagirma turu
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    answer = msg.content or "(bos yanit)"
                    self.chat_history.append({"role": "user", "content": user_text})
                    self.chat_history.append({"role": "assistant", "content": answer})
                    self._save_chat_history()
                    self.after(0, lambda: self._append_chat("Arkana Yaslan", answer, "assistant"))
                    self._speak(answer)
                    return

                messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                    tc.model_dump() for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {}
                    result = self._execute_tool(tc.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)[:4000]})
                resp = client.chat.completions.create(model=model, messages=messages, tools=TOOL_SCHEMAS,
                                                       max_tokens=800)

            self.after(0, lambda: self._append_chat("Arkana Yaslan", "Cok fazla arac adimi oldu, durduruyorum.",
                                                      "assistant"))
        except Exception as e:
            self.after(0, lambda: self._append_chat("Arkana Yaslan", f"Hata olustu: {e}", "assistant"))
        finally:
            self.after(0, lambda: self.send_btn.state(["!disabled"]))


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
