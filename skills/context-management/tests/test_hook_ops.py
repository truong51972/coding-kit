from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "hook_ops.py"
PROVIDER = SKILL_ROOT / "hooks" / "context_provider.py"


def _run(home: Path, operation: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "codex",
            operation,
            "--codex-home",
            str(home),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def _commands(config: dict) -> list[str]:
    commands: list[str] = []
    for groups in config.get("hooks", {}).values():
        for group in groups:
            for handler in group.get("hooks", []):
                command = handler.get("command")
                if isinstance(command, str):
                    commands.append(command)
    return commands


def test_install_preserves_unrelated_hooks_and_uses_installed_provider(tmp_path: Path) -> None:
    home = tmp_path / "codex"
    home.mkdir()
    target = home / "hooks.json"
    target.write_text(
        json.dumps(
            {
                "custom": {"keep": True},
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {"type": "command", "command": "echo unrelated"}
                            ]
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = _run(home, "install")

    assert result.returncode == 0, result.stderr
    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["custom"] == {"keep": True}
    commands = _commands(config)
    assert "echo unrelated" in commands
    managed = [command for command in commands if "--host claude-codex" in command]
    assert len(managed) == 2
    assert str(PROVIDER.resolve()) in managed[0]
    assert "${AGENTS_HOME" not in managed[0]


def test_install_is_idempotent(tmp_path: Path) -> None:
    home = tmp_path / "codex"

    first = _run(home, "install")
    second = _run(home, "install")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    config = json.loads((home / "hooks.json").read_text(encoding="utf-8"))
    managed = [
        command for command in _commands(config) if "--host claude-codex" in command
    ]
    assert len(managed) == 2


def test_status_and_remove_round_trip(tmp_path: Path) -> None:
    home = tmp_path / "codex"
    assert _run(home, "status").returncode == 1
    assert _run(home, "install").returncode == 0

    status = _run(home, "status")
    assert status.returncode == 0
    assert "installed:" in status.stdout

    removed = _run(home, "remove")
    assert removed.returncode == 0
    assert "removed:" in removed.stdout
    assert _run(home, "status").returncode == 1


def test_remove_preserves_unrelated_hooks(tmp_path: Path) -> None:
    home = tmp_path / "codex"
    assert _run(home, "install").returncode == 0
    target = home / "hooks.json"
    config = json.loads(target.read_text(encoding="utf-8"))
    config["hooks"].setdefault("Stop", []).append(
        {"hooks": [{"type": "command", "command": "echo keep-me"}]}
    )
    target.write_text(json.dumps(config), encoding="utf-8")

    result = _run(home, "remove")

    assert result.returncode == 0, result.stderr
    config = json.loads(target.read_text(encoding="utf-8"))
    assert "echo keep-me" in _commands(config)
    assert not any("--host claude-codex" in command for command in _commands(config))


def test_invalid_existing_json_fails_without_rewrite(tmp_path: Path) -> None:
    home = tmp_path / "codex"
    home.mkdir()
    target = home / "hooks.json"
    original = "{not-json\n"
    target.write_text(original, encoding="utf-8")

    result = _run(home, "install")

    assert result.returncode == 2
    assert target.read_text(encoding="utf-8") == original
