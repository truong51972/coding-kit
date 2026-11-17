#!/usr/bin/env python3
"""Bounded, opt-in REFLECT signals for Claude Code / Codex hook adapters.

Never reads transcript text, calls an LLM, or mutates repository memory.
The host-specific provider is responsible for formatting hook output.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"})
MEMORY_SEGMENTS = (".agents/contexts/", ".agents/experiences/", ".agents/assumptions/")
REASON = (
    "Run one bounded Context Management REFLECT before finalizing. Inspect only "
    "material knowledge/assumption deltas from this turn. Verify owning sources; "
    "respect the original request's read-only constraints. Use SYNC, verified "
    "CAPTURE, or TRACK_ASSUMPTION only when justified. NO_CHANGE is valid and "
    "must not create files. Do not repeat reflection after this continuation."
)
PROMPT_REMINDER = (
    "Context Management: after substantive work, run a bounded REFLECT on "
    "material current facts, verified lessons and decision-relevant unresolved "
    "assumptions. NO_CHANGE is normal; do not write memory for read-only tasks "
    "or promote an unsupported assumption."
)
COMPACT = (
    "Context Management: preserve concise pointers to unresolved, consequential "
    "assumptions and unprocessed knowledge candidates, with evidence and scope. "
    "Do not claim REFLECT/SYNC ran merely because this compaction hook fired. "
    "Do not copy entire context shards or tool transcripts into the summary."
)


def _state_path(root: Path, payload: dict[str, Any], host: str) -> Path | None:
    session = payload.get("session_id")
    if not isinstance(session, str) or not session or len(session) > 256:
        return None
    parent = Path(os.environ.get(
        "XDG_STATE_HOME", str(Path.home() / ".local" / "state")
    )) / "coding-kit" / "reflection-guard"
    key = hashlib.sha256(
        (str(root.resolve()) + "\0" + host + "\0" + session).encode()
    ).hexdigest()
    return parent / (key + ".json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".reflect-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _memory_only(tool_input: Any) -> bool:
    """Known memory writes must not schedule a second reflection loop."""
    if not isinstance(tool_input, dict):
        return False
    targets = [
        tool_input.get("file_path"), tool_input.get("path"),
        tool_input.get("notebook_path"),
    ]
    patch = tool_input.get("patch") or tool_input.get("patch_text") or tool_input.get("patchText")
    if isinstance(patch, str):
        targets += re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", patch, re.M)
    paths = [str(x).replace("\\", "/").removeprefix("./") for x in targets if isinstance(x, str)]
    if not paths:
        return False
    return all(
        any(("/" + p).find("/" + m) >= 0 for m in MEMORY_SEGMENTS)
        or any(p.startswith(m) for m in MEMORY_SEGMENTS)
        for p in paths
    )


def handle(root: Path, payload: dict[str, Any], host: str) -> dict[str, Any] | str | None:
    """Handle PostToolUse, Stop and PreCompact. Return output or None (silent)."""
    event = payload.get("hook_event_name")
    if event not in {"PostToolUse", "Stop", "PreCompact", "UserPromptSubmit"}:
        return None

    path = _state_path(root, payload, host)
    if path is None:
        return None
    current = _read(path)
    turn = payload.get("turn_id")
    turn = turn if isinstance(turn, str) and len(turn) < 256 else None

    if event == "UserPromptSubmit":
        # Codex presents a Stop-hook continuation as a new user-style prompt.
        # It must NOT reset the guard; otherwise reflection writes could trigger
        # a second continuation in the same logical turn.
        prompt = payload.get("prompt")
        if isinstance(prompt, str) and REASON[:55] in prompt:
            if current.get("requested"):
                _save(path, {"pending": False, "requested": True,
                             "turn": turn or current.get("turn")})
            return None
        # A genuinely new prompt opens a new opportunity. No prompt body is
        # persisted: state contains only turn IDs and Boolean flags.
        _save(path, {"pending": False, "requested": False, "turn": turn})
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": PROMPT_REMINDER,
            }
        }

    if event == "PostToolUse":
        tool = payload.get("tool_name")
        if payload.get("permission_mode") == "plan":
            return None
        if payload.get("is_error") is True or payload.get("tool_error"):
            return None
        if tool in ("Bash", "PowerShell") and host == "claude":
            # Claude 2.1.269+ may attach a best-effort changed-files diff.
            # Ignore shell commands without observed changes; never infer writes
            # by grepping command text (which could contain secrets).
            response = payload.get("tool_response")
            diff = response.get("bashEditDiff") if isinstance(response, dict) else None
            if not isinstance(diff, dict):
                return None
            paths = diff.get("changedFiles")
            if not isinstance(paths, list):
                return None
            touched = [p for p in paths if isinstance(p, str)]
            if not touched:
                return None
            if all(_memory_only({"path": p}) for p in touched):
                if current.get("pending"):
                    _save(path, {"pending": False, "requested": True,
                                 "turn": turn or current.get("turn")})
                return None
        elif tool in WRITE_TOOLS:
            if _memory_only(payload.get("tool_input")):
                if current.get("pending"):
                    _save(path, {"pending": False, "requested": True,
                                 "turn": turn or current.get("turn")})
                return None
        else:
            return None
        # No transcript or tool payload is stored: only a turn-scoped dirty bit.
        # Never reset the processed marker after a stop-hook continuation.
        if turn is not None and current.get("turn") != turn:
            current = {}
        if current.get("requested") and (turn is None or current.get("turn") == turn):
            return None
        _save(path, {"pending": True, "requested": False, "turn": turn})
        return None

    if event == "PreCompact":
        if current.get("pending"):
            if host == "claude":
                return COMPACT
            # Codex PreCompact has no summary-instruction channel; don't pretend
            # 'systemMessage' persists as part of the checkpoint.
        return None

    if payload.get("stop_hook_active") is True:
        # This is the one permitted continuation. No Stop-loop feedback.
        if current.get("pending") or current.get("requested"):
            _save(path, {"pending": False, "requested": True, "turn": turn})
        return None
    if payload.get("permission_mode") == "plan":
        return None
    if not current.get("pending") or current.get("requested"):
        return None
    if turn is not None and current.get("turn") not in (None, turn):
        # Old stale dirty event from a previous turn.
        return None
    # Consume BEFORE asking the host to continue: duplicate Stop is a no-op.
    _save(path, {"pending": False, "requested": True, "turn": turn})
    return {"decision": "block", "reason": REASON}
