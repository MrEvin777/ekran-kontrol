"""Merkezi arac kaydi: arkana_v2.TOOL_SCHEMAS + CONFIRM_REQUIRED'i, istenen
metadata seklinde (ad, aciklama, input semasi, izin seviyesi, risk seviyesi,
timeout, log) tek bir yerden okunabilir hale getirir. arkana_v2.py'nin kendi
TOOL_SCHEMAS'ini SILMEZ/degistirmez -- onun uzerine ince bir katman.
"""

from __future__ import annotations

import arkana_v2

CATEGORY_BY_TOOL = {
    "web_search": "web", "open_url": "web", "browser_navigate": "web", "browser_read_page": "web",
    "browser_click": "web", "browser_type": "web",
    "git_status": "github", "git_commit": "github", "git_push": "github", "git_diff": "github",
    "read_file": "dosya sistemi", "write_file": "dosya sistemi", "delete_file": "dosya sistemi",
    "list_dir": "dosya sistemi", "search_files": "dosya sistemi",
    "run_command": "powershell",
    "click": "pyautogui", "type_text": "pyautogui", "hotkey": "pyautogui", "scroll": "pyautogui",
    "get_active_window": "pyautogui", "list_open_windows": "pyautogui", "get_ui_elements": "pyautogui",
    "click_element": "pyautogui",
    "ocr_screen": "ocr",
    "memory_save": "hafiza", "memory_search": "hafiza",
    "delegate_to_agent": "kod analizi",
    "mcp_list_tools": "model saglayicilari", "mcp_call_tool": "model saglayicilari",
    "read_document": "dokumantasyon", "send_email": "web",
    "get_clipboard": "dosya sistemi", "set_clipboard": "dosya sistemi",
    "open_app": "pyautogui",
}

RISK_BY_TOOL = {
    "run_command": "yuksek", "git_push": "yuksek", "send_email": "yuksek", "delete_file": "orta",
    "write_file": "orta",
}

TIMEOUT_S_BY_TOOL = {
    "run_command": 60, "web_search": 30, "read_document": 30, "browser_navigate": 20,
    "delegate_to_agent": 180, "mcp_call_tool": 30,
}
DEFAULT_TIMEOUT_S = 15


def build_registry() -> list[dict]:
    registry = []
    for schema in arkana_v2.TOOL_SCHEMAS:
        fn = schema["function"]
        name = fn["name"]
        registry.append({
            "name": name,
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {}),
            "category": CATEGORY_BY_TOOL.get(name, "diger"),
            "permission_level": "onay_gerekli" if name in arkana_v2.CONFIRM_REQUIRED else "otomatik",
            "risk_level": RISK_BY_TOOL.get(name, "dusuk"),
            "timeout_s": TIMEOUT_S_BY_TOOL.get(name, DEFAULT_TIMEOUT_S),
            "logged": True,  # arkana_v2._execute_tool -> _log_tool + error_log.log_error hepsi icin gecerli
        })
    return registry


def get_tool(name: str) -> dict | None:
    for entry in build_registry():
        if entry["name"] == name:
            return entry
    return None
