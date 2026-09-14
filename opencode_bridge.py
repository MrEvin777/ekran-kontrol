"""OpenCode bridge: real coding/terminal agent via the installed `opencode` CLI.
Subprocess-based (matches free-llm-hub's proven pattern for this exact CLI):
`opencode run --format json` emits one JSON event per line, stdin closed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def _opencode_env() -> dict:
    """opencode needs its OWN provider key env vars (separate from arkana_v2's
    own config.json) -- it defaults to Google/Gemini and reads
    GOOGLE_GENERATIVE_AI_API_KEY, not GOOGLE_API_KEY. Map from the .env this
    machine already has, scoped to just this subprocess (never touches the
    real OS environment)."""
    env = os.environ.copy()
    if "GOOGLE_GENERATIVE_AI_API_KEY" not in env:
        env_file = Path(r"C:\ClaudeSistem\.env")
        if env_file.exists():
            m = re.search(r"^GOOGLE_API_KEY=(.+)$", env_file.read_text(encoding="utf-8"), re.MULTILINE)
            if m:
                env["GOOGLE_GENERATIVE_AI_API_KEY"] = m.group(1).strip()
    return env


def is_available() -> bool:
    return shutil.which("opencode") is not None


DEFAULT_MODEL = "google/gemini-3.1-flash-lite"  # GERCEKTEN test edildi, dosya olusturdu -- ucretsiz DEGIL
# (~$0.01/cagri, google_api_key'in kotasindan). "gemini-3-pro-image" (opencode'un
# kendi varsayilani) sifir ucretsiz kotaya sahip, bu yuzden onun yerine kullanildi.


def run_task(prompt: str, cwd: str, timeout_s: int = 120, model: str | None = DEFAULT_MODEL) -> dict:
    """One-shot: runs `opencode run` in `cwd`, returns the final text output plus
    every tool_use event seen (for the caller to log/checkpoint)."""
    exe = shutil.which("opencode")
    if exe is None:
        return {"ok": False, "error": "opencode CLI kurulu degil (npm install -g opencode-ai)"}
    try:
        # Windows: shutil.which resolves the real opencode.cmd path -- passing the
        # bare "opencode" string to subprocess.run fails with WinError 2, since
        # CreateProcess (unlike cmd.exe) does not apply PATHEXT resolution itself.
        args = [exe, "run", "--format", "json"]
        if model:
            args += ["--model", model]
        args.append(prompt)
        env = _opencode_env()
        # opencode resolves its project root from the inherited PWD env var, not
        # from the OS process cwd -- without this it silently writes into
        # whatever directory this Python process's PWD happened to be (a real bug
        # this caught: subprocess cwd=tmp_path, but opencode wrote into
        # C:\Users\muslu\OmniAI because that was the parent shell's stale PWD).
        env["PWD"] = cwd
        proc = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=timeout_s, stdin=subprocess.DEVNULL,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"opencode {timeout_s}s icinde bitmedi"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    events = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue

    # Real observed shape (opencode 1.18.26): {"type":"tool_use","part":{"type":
    # "tool","tool":"write","state":{"input":{...},"output":"..."}}} and
    # {"type":"text","part":{"type":"text","text":"..."}} -- the payload is
    # nested under "part", not at the event's top level.
    tool_events = [e for e in events if e.get("type") == "tool_use"]
    text_events = [e for e in events if e.get("type") == "text"]
    error_events = [e for e in events if e.get("type") == "error"]
    final_text = "".join(e.get("part", {}).get("text", "") for e in text_events)

    # opencode exits 0 even on a provider/auth error -- the JSON stream is the
    # real signal, not the process exit code.
    ok = proc.returncode == 0 and not error_events
    error_summary = "; ".join(e.get("error", {}).get("message", str(e.get("error"))) for e in error_events)

    tool_calls = []
    for e in tool_events:
        part = e.get("part", {})
        state = part.get("state", {})
        tool_calls.append({"name": part.get("tool"), "input": state.get("input"), "output": state.get("output")})

    return {
        "ok": ok,
        "text": final_text,
        "tool_calls": tool_calls,
        "returncode": proc.returncode,
        "error": error_summary if error_events else None,
        "stderr": proc.stderr[-2000:] if proc.returncode != 0 else "",
    }
