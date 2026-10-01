from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "hook_ops.py"
PROVIDER = SKILL_ROOT / "hooks" / "context_provider.py"


def _run(
    operation: str,
    *,
    cwd: Path,
    scope: str | None = None,
    codex_home: Path | None = None,
    project_root: Path | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT)]
    if stdin is None:
        command += ["codex", operation]
        if scope is not None:
            command += ["--scope", scope]
        if codex_home is not None:
            command += ["--codex-home", str(codex_home)]
        if project_root is not None:
            command += ["--project-root", str(project_root)]
    return subprocess.run(
        command,
        cwd=cwd,
        input=stdin,
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


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_default_scope_installs_project_hook(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    result = _run("install", cwd=repo)

    assert result.returncode == 0, result.stderr
    target = repo / ".codex" / "hooks.json"
    assert target.exists()
    config = json.loads(target.read_text(encoding="utf-8"))
    managed = [c for c in _commands(config) if "--host claude-codex" in c]
    assert len(managed) == 2
    assert str(PROVIDER.resolve()) in managed[0]


def test_global_scope_uses_codex_home(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "codex-home"

    result = _run("install", cwd=repo, scope="global", codex_home=home)

    assert result.returncode == 0, result.stderr
    assert (home / "hooks.json").exists()
    assert not (repo / ".codex" / "hooks.json").exists()


def test_project_root_override_works_outside_git(tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    project = tmp_path / "project"

    result = _run("install", cwd=cwd, project_root=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".codex" / "hooks.json").exists()


def test_install_is_idempotent_and_preserves_unrelated_hooks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    target = repo / ".codex" / "hooks.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps(
            {
                "custom": {"keep": True},
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "echo unrelated"}]}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    first = _run("install", cwd=repo)
    second = _run("install", cwd=repo)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["custom"] == {"keep": True}
    commands = _commands(config)
    assert "echo unrelated" in commands
    assert len([c for c in commands if "--host claude-codex" in c]) == 2


def test_status_and_remove_default_to_project(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    assert _run("status", cwd=repo).returncode == 1
    assert _run("install", cwd=repo).returncode == 0
    assert _run("status", cwd=repo).returncode == 0
    assert _run("remove", cwd=repo).returncode == 0
    assert _run("status", cwd=repo).returncode == 1


def test_menu_defaults_to_install_project(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    result = _run("", cwd=repo, stdin="\n\n")

    assert result.returncode == 0, result.stderr
    assert "Action:" in result.stdout
    assert "Scope:" in result.stdout
    assert "target:" in result.stdout
    assert (repo / ".codex" / "hooks.json").exists()


def test_invalid_existing_json_fails_without_rewrite(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    target = repo / ".codex" / "hooks.json"
    target.parent.mkdir()
    original = "{not-json\n"
    target.write_text(original, encoding="utf-8")

    result = _run("install", cwd=repo)

    assert result.returncode == 2
    assert target.read_text(encoding="utf-8") == original


def test_codex_home_rejected_for_project_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    result = _run("install", cwd=repo, codex_home=tmp_path / "home")
    assert result.returncode == 2
    assert "--codex-home is only valid with --scope global" in result.stderr
