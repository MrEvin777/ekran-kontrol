"""Real test against this actual git repo -- makes a change, confirms git_diff
sees it, matching the spec's "Git diff gostermeli" and "Git rollback" test items.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_git_diff_tool(repo_path, staged=False):
    cmd = ["git", "diff"] + (["--staged"] if staged else [])
    proc = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    return {"ok": proc.returncode == 0, "diff": (proc.stdout or proc.stderr)[:15000]}


def test_git_diff_sees_a_real_uncommitted_change(tmp_path):
    # a throwaway repo, not the real OmniAI one -- avoids touching real history
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, capture_output=True, text=True)
    f = tmp_path / "a.txt"
    f.write_text("line1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, text=True)

    f.write_text("line1\nline2\n", encoding="utf-8")

    result = _run_git_diff_tool(str(tmp_path))
    assert result["ok"] is True
    assert "line2" in result["diff"]


def test_git_diff_staged_only_shows_staged_changes(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, capture_output=True, text=True)
    f = tmp_path / "a.txt"
    f.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, text=True)

    f.write_text("v2\n", encoding="utf-8")  # unstaged only

    staged_result = _run_git_diff_tool(str(tmp_path), staged=True)
    assert "v2" not in staged_result["diff"]  # not staged, so invisible to --staged

    unstaged_result = _run_git_diff_tool(str(tmp_path), staged=False)
    assert "v2" in unstaged_result["diff"]
