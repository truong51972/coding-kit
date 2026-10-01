#!/usr/bin/env python3
"""Temporary runtime-hook installer until portable skill installers register hooks."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "hooks" / "context_provider.py"
CLAUDE_CODEX = ROOT / "hooks" / "claude-codex-hooks.json"
ANTIGRAVITY = ROOT / "hooks" / "antigravity-hooks.json"
OPENCODE = {1: ROOT / "hooks" / "opencode" / "v1.ts", 2: ROOT / "hooks" / "opencode" / "v2.ts"}

PROVIDERS = ("codex", "claude", "antigravity", "opencode")
NAMES = {
    "codex": "Codex",
    "claude": "Claude Code",
    "antigravity": "Antigravity / AGY",
    "opencode": "OpenCode",
}
REQUIRED_EVENTS = {"SessionStart", "SubagentStart"}


class HookError(ValueError):
    pass


def _project_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except OSError:
        pass
    return Path.cwd().resolve()


def _scope(value: str) -> str:
    if value == "project":
        return value
    if value in ("local", "global"):
        return "local"
    raise HookError(f"unsupported scope: {value}")


def _codex_home(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _target(
    provider: str,
    scope: str,
    *,
    project_root: str | None = None,
    codex_home: str | None = None,
) -> Path:
    project = _project_root(project_root)
    if _scope(scope) == "project":
        return {
            "codex": project / ".codex" / "hooks.json",
            "claude": project / ".claude" / "settings.json",
            "antigravity": project / ".agents" / "hooks.json",
            "opencode": project / ".opencode" / "plugins" / "context-management.ts",
        }[provider]
    return {
        "codex": _codex_home(codex_home) / "hooks.json",
        "claude": Path.home() / ".claude" / "settings.json",
        "antigravity": Path.home() / ".gemini" / "config" / "hooks.json",
        "opencode": Path.home() / ".config" / "opencode" / "plugins" / "context-management.ts",
    }[provider]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HookError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HookError(f"top-level JSON must be an object: {path}")
    return value


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _command(host: str) -> str:
    if not PROVIDER.is_file():
        raise HookError(f"provider missing: {PROVIDER}; reinstall/update the skill")
    args = [sys.executable, str(PROVIDER.resolve()), "--host", host]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


def _load_template(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise HookError(f"hook asset missing: {path}; reinstall/update the skill")
    return _load_json(path)


def _is_managed(handler: Any, host: str) -> bool:
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    command = handler.get("command")
    return (
        isinstance(command, str)
        and "context_provider.py" in command.replace("\\", "/")
        and f"--host {host}" in command
    )


def _strip_event_hooks(config: dict[str, Any], host: str) -> tuple[dict[str, Any], int]:
    updated = copy.deepcopy(config)
    hooks = updated.get("hooks")
    if hooks is None:
        return updated, 0
    if not isinstance(hooks, dict):
        raise HookError("existing 'hooks' field must be an object")
    removed = 0
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            raise HookError(f"hook event {event!r} must contain a list")
        kept = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept.append(group)
                continue
            handlers = [h for h in group["hooks"] if not _is_managed(h, host)]
            removed += len(group["hooks"]) - len(handlers)
            if handlers:
                item = copy.deepcopy(group)
                item["hooks"] = handlers
                kept.append(item)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        updated.pop("hooks", None)
    return updated, removed


def _event_template() -> dict[str, list[Any]]:
    template = _load_template(CLAUDE_CODEX)
    hooks = copy.deepcopy(template.get("hooks"))
    if not isinstance(hooks, dict):
        raise HookError("Claude/Codex template has no hooks object")
    command = _command("claude-codex")
    replaced = 0
    for groups in hooks.values():
        for group in groups if isinstance(groups, list) else []:
            for handler in group.get("hooks", []) if isinstance(group, dict) else []:
                if _is_managed(handler, "claude-codex"):
                    handler["command"] = command
                    replaced += 1
    if not replaced:
        raise HookError("Claude/Codex template has no managed command")
    return hooks


def _event_install(target: Path) -> int:
    try:
        current = _load_json(target)
        updated, removed = _strip_event_hooks(current, "claude-codex")
        desired = _event_template()
        hooks = updated.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise HookError("existing 'hooks' field must be an object")
        for event, groups in desired.items():
            hooks.setdefault(event, []).extend(copy.deepcopy(groups))
        _write_json(target, updated)
    except (HookError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{'updated' if removed else 'installed'}: Context Management hooks -> {target}")
    print(f"provider: {PROVIDER.resolve()}")
    return 0


def _event_status(target: Path) -> int:
    try:
        config = _load_json(target)
    except HookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    events = set()
    for event, groups in config.get("hooks", {}).items() if isinstance(config.get("hooks"), dict) else []:
        if any(
            _is_managed(handler, "claude-codex")
            for group in groups if isinstance(group, dict)
            for handler in group.get("hooks", []) if isinstance(group.get("hooks"), list)
        ):
            events.add(event)
    if REQUIRED_EVENTS.issubset(events):
        if not PROVIDER.is_file():
            print(f"broken: provider missing: {PROVIDER}")
            return 2
        print(f"installed: Context Management hooks in {target}")
        return 0
    print(f"{'partial' if events else 'not installed'}: Context Management hooks in {target}")
    return 1


def _event_remove(target: Path) -> int:
    try:
        current = _load_json(target)
        updated, removed = _strip_event_hooks(current, "claude-codex")
        if removed:
            _write_json(target, updated)
    except (HookError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"{'removed' if removed else 'not installed'}: Context Management hooks "
        f"{'from' if removed else 'in'} {target}"
    )
    return 0


def _antigravity_block() -> dict[str, Any]:
    block = copy.deepcopy(_load_template(ANTIGRAVITY).get("context-management"))
    if not isinstance(block, dict):
        raise HookError("Antigravity template has no context-management block")
    command = _command("antigravity")
    replaced = 0
    for groups in block.values():
        for group in groups if isinstance(groups, list) else []:
            if isinstance(group, dict) and group.get("type") == "command":
                group["command"] = command
                replaced += 1
    if not replaced:
        raise HookError("Antigravity template has no command hook")
    return block


def _antigravity_run(operation: str, target: Path) -> int:
    try:
        config = _load_json(target)
        installed = isinstance(config.get("context-management"), dict)
        if operation == "status":
            state = "installed" if installed else "not installed"
            if installed and not PROVIDER.is_file():
                state = "broken"
            print(f"{state}: Context Management Antigravity hooks in {target}")
            return 0 if state == "installed" else (2 if state == "broken" else 1)
        if operation == "install":
            config["context-management"] = _antigravity_block()
            _write_json(target, config)
            print(f"{'updated' if installed else 'installed'}: Context Management Antigravity hooks -> {target}")
            return 0
        if installed:
            config.pop("context-management")
            _write_json(target, config)
        print(f"{'removed' if installed else 'not installed'}: Context Management Antigravity hooks in {target}")
        return 0
    except (HookError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _opencode_major(explicit: int | None) -> int | None:
    if explicit in (1, 2):
        return explicit
    exe = shutil.which("opencode")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], text=True, capture_output=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"\b([12])(?:\.\d+)+\b", out.stdout + out.stderr)
    return int(match.group(1)) if match else None


def _opencode_known(text: str) -> bool:
    return any(asset.is_file() and asset.read_text(encoding="utf-8") == text for asset in OPENCODE.values())


def _opencode_run(operation: str, target: Path, major: int | None) -> int:
    existing = target.read_text(encoding="utf-8") if target.is_file() else None
    if operation == "status":
        state = "installed" if existing is not None and _opencode_known(existing) else (
            "conflict" if existing is not None else "not installed"
        )
        print(f"{state}: Context Management OpenCode plugin in {target}")
        return 0 if state == "installed" else (2 if state == "conflict" else 1)
    if operation == "remove":
        if existing is None:
            print(f"not installed: Context Management OpenCode plugin in {target}")
            return 0
        if not _opencode_known(existing):
            print(f"error: refusing to remove modified plugin: {target}", file=sys.stderr)
            return 2
        target.unlink()
        print(f"removed: Context Management OpenCode plugin from {target}")
        return 0
    major = _opencode_major(major)
    if major is None:
        print("error: cannot detect OpenCode major; use --opencode-major 1 or 2", file=sys.stderr)
        return 2
    asset = OPENCODE[major]
    if not asset.is_file():
        print(f"error: adapter missing: {asset}", file=sys.stderr)
        return 2
    desired = asset.read_text(encoding="utf-8")
    if existing is not None and existing != desired and not _opencode_known(existing):
        print(f"error: refusing to overwrite modified plugin: {target}", file=sys.stderr)
        return 2
    _write(target, desired)
    print(f"{'updated' if existing is not None else 'installed'}: Context Management OpenCode v{major} plugin -> {target}")
    return 0


def _detected(provider: str, project: Path) -> bool:
    dirs = {
        "codex": (project / ".codex", Path.home() / ".codex"),
        "claude": (project / ".claude", Path.home() / ".claude"),
        "antigravity": (project / ".agents" / "hooks.json", Path.home() / ".gemini"),
        "opencode": (project / ".opencode", Path.home() / ".config" / "opencode"),
    }[provider]
    bins = {
        "codex": ("codex",),
        "claude": ("claude",),
        "antigravity": ("agy", "antigravity"),
        "opencode": ("opencode",),
    }[provider]
    return any(path.exists() for path in dirs) or any(shutil.which(name) for name in bins)


def _scan(project: Path) -> list[tuple[str, bool]]:
    result = [(provider, _detected(provider, project)) for provider in PROVIDERS]
    return sorted(result, key=lambda item: (not item[1], PROVIDERS.index(item[0])))


def _section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    print("  " + "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers)))
    print("  " + "  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  " + "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


def _choose(title: str, options: list[tuple[str, str]], default: str) -> str:
    _section(title)
    rows = [
        (str(i), label, "default" if value == default else "")
        for i, (value, label) in enumerate(options, 1)
    ]
    _table(("#", "Option", ""), rows)
    default_index = next(i for i, (value, _) in enumerate(options, 1) if value == default)
    raw = input(f"\nChoice [{default_index}]: ").strip().lower()
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1][0]
    if raw in {value for value, _ in options}:
        return raw
    raise HookError(f"invalid choice: {raw}")


def _choose_provider(
    scanned: list[tuple[str, bool]], default: str
) -> str:
    _section("2) Provider")
    rows = []
    for index, (name, detected) in enumerate(scanned, 1):
        rows.append(
            (
                str(index),
                NAMES[name],
                "detected" if detected else "-",
                "recommended" if name == default else "",
            )
        )
    _table(("#", "Provider", "Status", "Recommendation"), rows)
    default_index = next(i for i, (name, _) in enumerate(scanned, 1) if name == default)
    raw = input(f"\nChoice [{default_index}]: ").strip().lower()
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(scanned):
        return scanned[int(raw) - 1][0]
    if raw in {name for name, _ in scanned}:
        return raw
    raise HookError(f"invalid choice: {raw}")


def _quick_state(provider: str, target: Path) -> str:
    if provider in ("codex", "claude"):
        try:
            config = _load_json(target)
        except HookError:
            return "broken config"
        events = set()
        hooks = config.get("hooks")
        if isinstance(hooks, dict):
            for event, groups in hooks.items():
                if isinstance(groups, list) and any(
                    _is_managed(handler, "claude-codex")
                    for group in groups if isinstance(group, dict)
                    for handler in group.get("hooks", []) if isinstance(group.get("hooks"), list)
                ):
                    events.add(event)
        return "installed" if REQUIRED_EVENTS.issubset(events) else ("partial" if events else "not installed")
    if provider == "antigravity":
        try:
            return "installed" if isinstance(_load_json(target).get("context-management"), dict) else "not installed"
        except HookError:
            return "broken config"
    if target.is_file():
        try:
            return "installed" if _opencode_known(target.read_text(encoding="utf-8")) else "custom/conflict"
        except OSError:
            return "broken"
    return "not installed"


def _interactive() -> tuple[str, str, str, int | None]:
    project = _project_root()
    print()
    print("Context Management Hooks")
    print("========================")
    _table(("Context", "Value"), [("Project", str(project)), ("Provider asset", "ready" if PROVIDER.is_file() else "missing")])

    scope = _choose(
        "1) Scope",
        [("project", "Project — this repository"), ("local", "Local — all projects on this machine")],
        "project",
    )

    scanned = _scan(project)
    recommended = next((name for name, found in scanned if found), "codex")
    provider = _choose_provider(scanned, recommended)

    target = _target(provider, scope)
    state = _quick_state(provider, target)
    _section("Selection")
    _table(
        ("Field", "Value"),
        [
            ("Scope", "Project" if scope == "project" else "Local"),
            ("Provider", NAMES[provider]),
            ("State", state),
            ("Target", str(target)),
        ],
    )

    operation = _choose(
        "3) Action",
        [("install", "Install / update"), ("status", "Show status"), ("remove", "Remove")],
        "install",
    )

    major = None
    if provider == "opencode" and operation == "install":
        major = _opencode_major(None)
        if major is None:
            major = int(_choose("OpenCode major", [("2", "V2"), ("1", "V1")], "2"))
        else:
            _section("OpenCode")
            print(f"  Detected major version: v{major}")
    print()
    return provider, operation, scope, major


def _run(provider: str, operation: str, target: Path, major: int | None = None) -> int:
    if provider in ("codex", "claude"):
        return {"install": _event_install, "status": _event_status, "remove": _event_remove}[operation](target)
    if provider == "antigravity":
        return _antigravity_run(operation, target)
    return _opencode_run(operation, target, major)


def main() -> int:
    if len(sys.argv) == 1:
        try:
            provider, operation, scope, major = _interactive()
            return _run(provider, operation, _target(provider, scope), major)
        except (EOFError, KeyboardInterrupt):
            print("\ncancelled")
            return 130
        except HookError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    parser = argparse.ArgumentParser(description="Manage Context Management runtime hooks.")
    parser.add_argument("provider", choices=PROVIDERS)
    parser.add_argument("operation", choices=("install", "status", "remove"))
    parser.add_argument("--scope", choices=("project", "local", "global"), default="project")
    parser.add_argument("--project-root")
    parser.add_argument("--codex-home")
    parser.add_argument("--opencode-major", type=int, choices=(1, 2))
    args = parser.parse_args()

    scope = _scope(args.scope)
    if args.codex_home and (args.provider != "codex" or scope == "project"):
        parser.error("--codex-home is only valid for Codex local/global scope")
    target = _target(
        args.provider,
        scope,
        project_root=args.project_root,
        codex_home=args.codex_home,
    )
    return _run(args.provider, args.operation, target, args.opencode_major)


if __name__ == "__main__":
    raise SystemExit(main())
