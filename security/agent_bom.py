
import json, time
from pathlib import Path
LOG = Path.home() / "OmniAI" / "security" / "agent_bom.jsonl"

def log_action(agent, action, tool, risk="low"):
    entry = {"ts": time.time(), "agent": agent, "action": action,
             "tool": tool, "risk": risk, "approved": risk != "critical"}
    with open(LOG, "a") as f: f.write(json.dumps(entry) + "\n")
    return entry
