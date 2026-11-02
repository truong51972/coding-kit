#!/usr/bin/env python3
"""Optional, advisory failure-loop guard. Stores only hashes/counters in user state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

LIMIT = 65536
THRESHOLD = 3
ERROR_LINE = re.compile(r"(?:\b(?:error|exception|fatal|failed|failure|traceback)\b|Error:)", re.I)
FAILED_COUNT = re.compile(r"\b(\d+)\s+failed\b", re.I)
EXIT_CODE = re.compile(r"(?:exit code|exit_code|exited with code)\s*[:=]?\s*(\d+)", re.I)
HINT = (
    "Potential failure loop: the same error signature appeared 3 times without "
    "observed progress. Stop repeating the approach. Inspect the owning source, "
    "compare the last attempts, and look up a relevant lesson with "
    "'python3 skills/context-management/scripts/experience_ops.py list --query <error>'. "
    "Experiences are advisory; verify against current source and tests."
)


def state_file(session: str, repo: str) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    parent = base / "coding-kit" / "experience-guard"
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256((repo + "\n" + session).encode("utf-8")).hexdigest()
    return parent / (digest + ".json")


def fingerprint(output: str, command: str) -> str | None:
    relevant = [line.strip() for line in output[-LIMIT:].splitlines()
                if ERROR_LINE.search(line) and line.strip()]
    if not relevant:
        return None
    line = relevant[-1][:400].casefold()
    line = re.sub(r"0x[0-9a-f]+", "0x#", line)
    line = re.sub(r"\b\d+\b", "#", line)
    line = re.sub(r"\s+", " ", line)
    family = "pytest" if "pytest" in command else "build" if any(
        x in command for x in ("build", "compile", "npm", "cargo")) else "general"
    return hashlib.sha256((family + ":" + line).encode("utf-8")).hexdigest()


def observe(*, session: str, repo: str, command: str, exit_code: int,
            output: str, threshold: int = THRESHOLD) -> str | None:
    """Return one advisory at threshold, never an instruction to block execution."""
    if not session or threshold < 2:
        return None
    path = state_file(session, repo)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - state.get("time", 0) > 86400:
            state = {}
    except (OSError, ValueError, TypeError):
        state = {}
    sig = fingerprint(output, command) if exit_code != 0 else None
    count_match = FAILED_COUNT.search(output[-LIMIT:])
    failed_count = int(count_match.group(1)) if count_match else None
    if not sig:
        new = {"signature": None, "streak": 0, "alerted": False}
    else:
        same = sig == state.get("signature")
        previous = state.get("failed_count")
        improvement = (same and isinstance(previous, int) and
                       failed_count is not None and failed_count < previous)
        streak = state.get("streak", 0) + 1 if same and not improvement else 1
        alerted = bool(state.get("alerted")) if same and not improvement else False
        new = {"signature": sig, "streak": min(streak, 1000),
               "alerted": alerted, "failed_count": failed_count}
    new["time"] = time.time()
    warn = bool(sig and new["streak"] >= threshold and not new["alerted"])
    if warn:
        new["alerted"] = True
    # Atomic replacement avoids partial reads. Per-agent session ids isolate workers.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                         prefix=".tmp-", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            json.dump(new, handle)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return HINT.replace("3 times", f"{threshold} times") if warn else None


def response_text(value: Any) -> str:
    if isinstance(value, str):
        return value[-LIMIT:]
    if isinstance(value, dict):
        parts = []
        for field in ("stdout", "stderr", "output", "error", "content"):
            if field in value:
                parts.append(response_text(value[field]))
        return "\n".join(parts)[-LIMIT:]
    if isinstance(value, list):
        return "\n".join(response_text(x) for x in value)[-LIMIT:]
    return ""


def handle_hook(payload: dict[str, Any]) -> dict[str, Any] | None:
    event = payload.get("hook_event_name")
    if event not in ("PostToolUse", "PostToolUseFailure"):
        return None
    # Only command-execution tools have meaningful process error semantics.
    if payload.get("tool_name") not in ("Bash", "exec_command"):
        return None
    session = payload.get("session_id")
    inputs = payload.get("tool_input")
    if not isinstance(session, str) or not isinstance(inputs, dict):
        return None
    command = inputs.get("command") or inputs.get("cmd") or ""
    if not isinstance(command, str):
        return None
    response = payload.get("tool_response", {})
    message = response_text(response)
    code = response.get("exit_code") if isinstance(response, dict) else None
    if not isinstance(code, int):
        match = EXIT_CODE.search(message)
        code = int(match.group(1)) if match else (1 if event == "PostToolUseFailure" else 0)
    if code == 0:
        # Some hosts do not expose an exit status; do not infer failure from text.
        return None
    reminder = observe(session=session, repo=str(payload.get("cwd", "")),
                       command=command, exit_code=code, output=message)
    if reminder:
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": reminder}}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    observer = sub.add_parser("observe", help="read command output from stdin")
    observer.add_argument("--session-id", required=True)
    observer.add_argument("--repo", default=os.getcwd())
    observer.add_argument("--command", required=True)
    observer.add_argument("--exit-code", type=int, required=True)
    observer.add_argument("--threshold", type=int, default=THRESHOLD)
    sub.add_parser("hook", help="read supported host PostToolUse JSON from stdin")
    args = parser.parse_args()
    try:
        data = sys.stdin.read(LIMIT * 4)
        if args.action == "observe":
            if args.threshold < 2:
                parser.error("--threshold must be >= 2")
            hint = observe(session=args.session_id, repo=args.repo,
                           command=args.command, exit_code=args.exit_code,
                           output=data, threshold=args.threshold)
            if hint:
                print(hint)
        else:
            payload = json.loads(data)
            if isinstance(payload, dict):
                hint = handle_hook(payload)
                if hint:
                    print(json.dumps(hint, separators=(",", ":")))
    except (OSError, ValueError, TypeError):
        # Failure guard must never interrupt an agent or obscure the real tool result.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
