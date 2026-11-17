"""Regression tests for host-specific, bounded REFLECT hook signaling."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROVIDER = Path(__file__).resolve().parents[1] / "hooks/context_provider.py"
START = "<!-- context-management:start -->"
END = "<!-- context-management:end -->"


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "AGENTS.md").write_text(
        f"# Project\n{START}\n## Context Management\n{END}\n", encoding="utf-8")
    return root


def _event(root: Path, home: Path, host: str, event: str, **extra: object):
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(home)
    payload = {"session_id": "s1", "cwd": str(root), "hook_event_name": event, **extra}
    result = subprocess.run(
        [sys.executable, str(PROVIDER), "--host", f"{host}-reflect"],
        cwd=root, env=env, input=json.dumps(payload), text=True,
        capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    if not result.stdout:
        return None
    if event == "PreCompact" and host == "claude":
        return result.stdout
    return json.loads(result.stdout)


def test_stop_is_once_per_substantive_write_turn(tmp_path: Path) -> None:
    root, home = _repo(tmp_path), tmp_path / "state"
    assert _event(root, home, "claude", "Stop") is None
    assert _event(root, home, "claude", "PostToolUse", tool_name="Edit",
                  tool_input={"file_path": "src/service.py"}) is None
    first = _event(root, home, "claude", "Stop")
    assert first["decision"] == "block"
    assert "NO_CHANGE" in first["reason"]
    assert _event(root, home, "claude", "Stop") is None
    assert _event(root, home, "claude", "Stop", stop_hook_active=True) is None
    # New user turn gets its own single bounded opportunity.
    assert _event(root, home, "claude", "UserPromptSubmit") is None
    assert _event(root, home, "claude", "PostToolUse", tool_name="Write",
                  tool_input={"file_path": "src/new.py"}) is None
    assert _event(root, home, "claude", "Stop")["decision"] == "block"


def test_reflect_memory_write_does_not_retrigger(tmp_path: Path) -> None:
    root, home = _repo(tmp_path), tmp_path / "state"
    _event(root, home, "codex", "PostToolUse", turn_id="turn-1",
           tool_name="Edit", tool_input={"file_path": "src/main.py"})
    assert _event(root, home, "codex", "Stop", turn_id="turn-1")["decision"] == "block"
    assert _event(root, home, "codex", "PostToolUse", turn_id="turn-1",
                  tool_name="Write", tool_input={"file_path": ".agents/contexts/project-baseline.md"}) is None
    assert _event(root, home, "codex", "Stop", turn_id="turn-1") is None
    # A different Codex turn has a distinct identity.
    _event(root, home, "codex", "PostToolUse", turn_id="turn-2",
           tool_name="Edit", tool_input={"file_path": "src/next.py"})
    assert _event(root, home, "codex", "Stop", turn_id="turn-2")["decision"] == "block"


def test_read_only_tools_and_plan_mode_do_not_trigger(tmp_path: Path) -> None:
    root, home = _repo(tmp_path), tmp_path / "state"
    _event(root, home, "codex", "PostToolUse", tool_name="Read",
           tool_input={"file_path": "src/main.py"})
    _event(root, home, "codex", "PostToolUse", tool_name="Edit",
           permission_mode="plan", tool_input={"file_path": "src/main.py"})
    assert _event(root, home, "codex", "Stop") is None


def test_precompact_is_nonblocking_and_does_not_claim_sync(tmp_path: Path) -> None:
    root, home = _repo(tmp_path), tmp_path / "state"
    _event(root, home, "claude", "PostToolUse", tool_name="Edit",
           tool_input={"file_path": "src/main.py"})
    output = _event(root, home, "claude", "PreCompact", trigger="auto")
    assert "unprocessed" in output and "Do not claim" in output
    # Still pending: precompact never consumes the Stop opportunity.
    assert _event(root, home, "claude", "Stop")["decision"] == "block"
    assert _event(root, home, "codex", "PreCompact", trigger="auto") is None


def test_invalid_marker_and_missing_session_are_silent(tmp_path: Path) -> None:
    root, home = _repo(tmp_path), tmp_path / "state"
    (root / "AGENTS.md").write_text(f"{START}\n{END}\n{START}\n{END}\n")
    assert _event(root, home, "claude", "Stop") is None
    (root / "AGENTS.md").write_text(f"# Repo\n{START}\n{END}\n")
    env = os.environ.copy()
    env["XDG_STATE_HOME"] = str(home)
    result = subprocess.run(
        [sys.executable, str(PROVIDER), "--host", "claude-reflect"],
        cwd=root, env=env, input=json.dumps({"hook_event_name": "Stop", "cwd": str(root)}),
        text=True, capture_output=True, check=False)
    assert result.returncode == 0 and not result.stdout


def test_no_tool_payload_or_raw_transcript_saved(tmp_path: Path) -> None:
    root, home = _repo(tmp_path), tmp_path / "state"
    _event(root, home, "claude", "PostToolUse", tool_name="Edit",
           tool_input={"file_path": "src/main.py", "secret": "private API token"})
    files = list(home.rglob("*.json"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "private API token" not in text
    assert "src/main.py" not in text
    assert json.loads(text)["pending"] is True
