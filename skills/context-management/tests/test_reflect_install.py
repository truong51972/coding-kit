"""Installer regressions for opt-in reflection without changing default hooks."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/hook_ops.py"


def _run(repo: Path, host: str, action: str, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), host, action, "--project-root", str(repo), *extra],
        cwd=repo, text=True, capture_output=True, check=False)


def _events(path: Path, keyword: str) -> set[str]:
    config = json.loads(path.read_text(encoding="utf-8"))
    return {
        event
        for event, groups in config["hooks"].items()
        if any(keyword in handler.get("command", "") for group in groups
               for handler in group.get("hooks", []))
    }


def test_codex_opt_in_install_upgrade_remove(tmp_path: Path) -> None:
    repo = tmp_path
    config = repo / ".codex/hooks.json"
    assert _run(repo, "codex", "install").returncode == 0
    assert _events(config, "--host codex-reflect") == set()
    assert _run(repo, "codex", "install", "--with-reflect").returncode == 0
    assert _events(config, "--host codex-reflect") == {
        "PostToolUse", "Stop", "UserPromptSubmit"}
    assert _run(repo, "codex", "install", "--with-reflect").returncode == 0
    assert "reflection: registered" in _run(repo, "codex", "status").stdout
    assert _run(repo, "codex", "install").returncode == 0
    assert _events(config, "--host codex-reflect") == set()
    assert _run(repo, "codex", "remove").returncode == 0
    assert not config.exists() or _events(config, "--host claude-codex") == set()


def test_claude_reflect_coexists_with_failure_guard(tmp_path: Path) -> None:
    repo = tmp_path
    config = repo / ".claude/settings.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"permissions": {"allow": ["Read"]}}))
    install = _run(repo, "claude", "install", "--with-reflect", "--with-failure-guard")
    assert install.returncode == 0, install.stderr
    assert _events(config, "--host claude-reflect") == {
        "PostToolUse", "Stop", "PreCompact", "UserPromptSubmit"}
    assert _events(config, "--host claude-codex") == {
        "SessionStart", "SubagentStart", "PostToolUse", "PostToolUseFailure"}
    assert json.loads(config.read_text())["permissions"] == {"allow": ["Read"]}
    assert "reflection: registered" in _run(repo, "claude", "status").stdout
    assert _run(repo, "claude", "remove").returncode == 0
    assert json.loads(config.read_text())["permissions"] == {"allow": ["Read"]}


def test_reject_reflection_on_unsupported_host(tmp_path: Path) -> None:
    assert _run(tmp_path, "antigravity", "install", "--with-reflect").returncode != 0
    assert _run(tmp_path, "opencode", "install", "--with-reflect").returncode != 0
