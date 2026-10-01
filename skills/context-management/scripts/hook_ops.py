#!/usr/bin/env python3
"""Install, inspect, or remove Context Management runtime hooks."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
HOOK_TEMPLATE = SKILL_ROOT / "hooks" / "claude-codex-hooks.json"
PROVIDER = SKILL_ROOT / "hooks" / "context_provider.py"
REQUIRED_CODEX_EVENTS = {"SessionStart", "SubagentStart"}


class HookConfigError(ValueError):
    pass


def _shell_command(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def _codex_home(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def _load_json(path: Path, *, missing_ok: bool = False) -> dict[str, Any]:
    if not path.exists():
        if missing_ok:
            return {}
        raise HookConfigError(f"missing JSON file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HookConfigError(f"cannot read valid JSON from {path}: {error}") from error
    if not isinstance(data, dict):
        raise HookConfigError(f"top-level JSON value must be an object: {path}")
    return data


def _desired_codex_hooks() -> dict[str, list[Any]]:
    template = _load_json(HOOK_TEMPLATE)
    hooks = copy.deepcopy(template.get("hooks"))
    if not isinstance(hooks, dict):
        raise HookConfigError(f"hook template has no hooks object: {HOOK_TEMPLATE}")

    command = _shell_command(
        [sys.executable, str(PROVIDER.resolve()), "--host", "claude-codex"]
    )
    replaced = 0
    for groups in hooks.values():
        if not isinstance(groups, list):
            raise HookConfigError("hook template event must contain a list")
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if not isinstance(handler, dict):
                    continue
                existing = handler.get("command")
                if (
                    handler.get("type") == "command"
                    and isinstance(existing, str)
                    and "context_provider.py" in existing
                    and "--host claude-codex" in existing
                ):
                    handler["command"] = command
                    replaced += 1
    if replaced == 0:
        raise HookConfigError("hook template contains no Context Management Codex command")
    return hooks


def _is_context_management_handler(handler: Any) -> bool:
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    normalized = command.replace("\\", "/")
    return "context_provider.py" in normalized and "--host claude-codex" in command


def _strip_context_management_hooks(config: dict[str, Any]) -> tuple[dict[str, Any], int]:
    updated = copy.deepcopy(config)
    hooks = updated.get("hooks")
    if hooks is None:
        return updated, 0
    if not isinstance(hooks, dict):
        raise HookConfigError("existing hooks.json field 'hooks' must be an object")

    removed = 0
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            raise HookConfigError(f"existing hooks.json event {event!r} must contain a list")
        kept_groups: list[Any] = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                kept_groups.append(group)
                continue
            kept_handlers = [
                handler for handler in handlers if not _is_context_management_handler(handler)
            ]
            removed += len(handlers) - len(kept_handlers)
            if kept_handlers:
                new_group = copy.deepcopy(group)
                new_group["hooks"] = kept_handlers
                kept_groups.append(new_group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]

    if not hooks:
        updated.pop("hooks", None)
    return updated, removed


def _managed_events(config: dict[str, Any]) -> set[str]:
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return set()
    events: set[str] = set()
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if isinstance(handlers, list) and any(
                _is_context_management_handler(handler) for handler in handlers
            ):
                events.add(event)
                break
    return events


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def codex_install(home: Path) -> int:
    target = home / "hooks.json"
    try:
        current = _load_json(target, missing_ok=True)
        updated, removed = _strip_context_management_hooks(current)
        desired = _desired_codex_hooks()
    except HookConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    hooks = updated.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        print("error: existing hooks.json field 'hooks' must be an object", file=sys.stderr)
        return 2
    for event, groups in desired.items():
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            print(f"error: existing hooks.json event {event!r} must contain a list", file=sys.stderr)
            return 2
        existing.extend(copy.deepcopy(groups))

    try:
        _atomic_write_json(target, updated)
    except OSError as error:
        print(f"error: cannot write {target}: {error}", file=sys.stderr)
        return 2

    action = "updated" if removed else "installed"
    print(f"{action}: Context Management Codex hooks -> {target}")
    print(f"provider: {PROVIDER.resolve()}")
    return 0


def codex_status(home: Path) -> int:
    target = home / "hooks.json"
    try:
        current = _load_json(target, missing_ok=True)
    except HookConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    events = _managed_events(current)
    if REQUIRED_CODEX_EVENTS.issubset(events):
        print(f"installed: Context Management Codex hooks in {target}")
        return 0
    if events:
        missing = ", ".join(sorted(REQUIRED_CODEX_EVENTS - events))
        print(f"partial: Context Management Codex hooks in {target}; missing {missing}")
        return 1
    print(f"not installed: Context Management Codex hooks in {target}")
    return 1


def codex_remove(home: Path) -> int:
    target = home / "hooks.json"
    try:
        current = _load_json(target, missing_ok=True)
        updated, removed = _strip_context_management_hooks(current)
    except HookConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if removed == 0:
        print(f"not installed: Context Management Codex hooks in {target}")
        return 0

    try:
        _atomic_write_json(target, updated)
    except OSError as error:
        print(f"error: cannot write {target}: {error}", file=sys.stderr)
        return 2
    print(f"removed: {removed} Context Management hook command(s) from {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage Context Management runtime hook registration."
    )
    parser.add_argument("host", choices=("codex",))
    parser.add_argument("operation", choices=("install", "status", "remove"))
    parser.add_argument(
        "--codex-home",
        help="Override CODEX_HOME/~/.codex for testing or custom installations.",
    )
    args = parser.parse_args()

    home = _codex_home(args.codex_home)
    if args.operation == "install":
        return codex_install(home)
    if args.operation == "status":
        return codex_status(home)
    return codex_remove(home)


if __name__ == "__main__":
    raise SystemExit(main())
