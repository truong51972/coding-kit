#!/usr/bin/env python3
"""Optional Claude-compatible hook: small experience index and loop guard."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from experience_ops import catalog, relevance, root  # noqa: E402
from failure_guard import handle_hook  # noqa: E402


def handle(payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    if event != "SessionStart":
        return handle_hook(payload)
    cwd = payload.get("cwd")
    repo = root(cwd if isinstance(cwd, str) else None)
    items = [m for m in catalog(repo, "both") if m["status"] == "active"]
    if not items:
        return None
    # Stable ordering, hard bound: no full contents or unbounded prompt injection.
    items = sorted(items, key=lambda m: m["name"])[:8]
    entries = "\n".join(f'- {m["name"]}: {m["description"]}' for m in items)
    message = (
        "Experience notebook (advisory historical lessons, source/tests win):\n"
        + entries +
        "\nFor other lessons use experience_ops.py list --query <topic>; "
        "use show <name> only if the lesson matches the task."
    )
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": message[:1800]}}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read(262144))
        if isinstance(payload, dict):
            result = handle(payload)
            if result is not None:
                print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError, TypeError):
        pass  # Hooks must not interrupt the host.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
