#!/usr/bin/env python3
"""Small host adapters that re-surface Context Management routing.

The hook deliberately does not read or inject context shards. It only restores
small routing/continuity reminders at host lifecycle boundaries. Semantic
UNDERSTAND/AUDIT/SYNC/MAINTENANCE behavior stays in the skill.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MANAGED_BLOCK_START = "<!-- context-management:start -->"
MANAGED_BLOCK_END = "<!-- context-management:end -->"

BOOTSTRAP_CONTEXT = (
    "Context Management is active in this repository. Read only the marker-managed "
    "Context Management block in AGENTS.md before non-trivial work. Use its Context "
    "Index to lazy-load only the shard needed next; verify decisions against owning "
    "source, which is authoritative. Hooks only restore routing/continuity; semantic "
    "audit, sync, and maintenance remain context-management skill behavior."
)

COMPACT_CONTEXT = (
    "Context Management continuity after compaction. Re-read the marker-managed "
    "block in AGENTS.md, then reload only the shard directly needed for the active "
    "task; do not bulk-load context. Treat owning source as authoritative and continue "
    "the existing task from the compacted summary. Audit, sync, and maintenance "
    "behavior remains unchanged and is not performed by this hook."
)

SUBAGENT_CONTEXT = (
    "Context Management applies in this subagent. Do not assume parent-loaded shards "
    "were inherited. Read the marker-managed block in AGENTS.md and lazy-load only the "
    "shard needed for this subtask; verify against owning source. Do not run audit or "
    "sync merely because this hook fired."
)


def _contains_managed_block(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    start = text.find(MANAGED_BLOCK_START)
    end = text.find(MANAGED_BLOCK_END)
    return start >= 0 and end > start


def _managed_root(starts: list[str]) -> Path | None:
    seen: set[Path] = set()
    for raw in starts:
        if not raw:
            continue
        try:
            current = Path(raw).expanduser().resolve()
        except OSError:
            continue
        if current.is_file():
            current = current.parent
        for candidate in (current, *current.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if _contains_managed_block(candidate / "AGENTS.md"):
                return candidate
    return None


def _starts_for(payload: dict[str, Any]) -> list[str]:
    starts: list[str] = []
    cwd = payload.get("cwd")
    if isinstance(cwd, str):
        starts.append(cwd)
    workspace_paths = payload.get("workspacePaths")
    if isinstance(workspace_paths, list):
        starts.extend(item for item in workspace_paths if isinstance(item, str))
    return starts


def _claude_codex(payload: dict[str, Any]) -> dict[str, Any] | None:
    if _managed_root(_starts_for(payload)) is None:
        return None

    event = payload.get("hook_event_name")
    if event == "SessionStart":
        context = COMPACT_CONTEXT if payload.get("source") == "compact" else BOOTSTRAP_CONTEXT
    elif event == "SubagentStart":
        context = SUBAGENT_CONTEXT
    else:
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": context,
        }
    }


def _antigravity(payload: dict[str, Any]) -> dict[str, Any]:
    # Antigravity has no SessionStart/compact event. PreInvocation is therefore used
    # only for invocation 0; later invocations remain a no-op despite the host calling
    # the command hook again.
    if payload.get("invocationNum") != 0:
        return {}
    if _managed_root(_starts_for(payload)) is None:
        return {}
    return {"injectSteps": [{"ephemeralMessage": BOOTSTRAP_CONTEXT}]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=("claude-codex", "antigravity"), required=True)
    args = parser.parse_args()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0

    output: dict[str, Any] | None
    if args.host == "claude-codex":
        output = _claude_codex(payload)
    else:
        output = _antigravity(payload)

    if output is not None:
        sys.stdout.write(json.dumps(output, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
