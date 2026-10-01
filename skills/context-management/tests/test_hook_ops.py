from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "hook_ops.py"
PROVIDER = SKILL_ROOT / "hooks" / "context_provider.py"


def _run(
    provider: str,
    operation: str,
    *,
    cwd: Path,
    scope: str | None = None,
    codex_home: Path | None = None,
    project_root: Path | None = None,
    opencode_major: int | None = None,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT)]
    if stdin is None:
        command += [provider, operation]
        if scope is not None:
            command += ["--scope", scope]
        if codex_home is not None:
            command += ["--codex-home", str(codex_home)]
        if project_root is not None:
            command += ["--project-root", str(project_root)]
        if opencode_major is not None:
            command += ["--opencode-major", str(opencode_major)]
    return subprocess.run(
        command,
        cwd=cwd,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        env=env,
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


def test_default_scope_installs_codex_project_hook(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    result = _run("codex", "install", cwd=repo)

    assert result.returncode == 0, result.stderr
    target = repo / ".codex" / "hooks.json"
    config = json.loads(target.read_text(encoding="utf-8"))
    managed = [c for c in _commands(config) if "--host claude-codex" in c]
    assert len(managed) == 2
    assert str(PROVIDER.resolve()) in managed[0]


def test_global_alias_still_uses_codex_home(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "codex-home"

    result = _run(
        "codex",
        "install",
        cwd=repo,
        scope="global",
        codex_home=home,
    )

    assert result.returncode == 0, result.stderr
    assert (home / "hooks.json").exists()
    assert not (repo / ".codex" / "hooks.json").exists()


def test_project_root_override_works_outside_git(tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    project = tmp_path / "project"

    result = _run("codex", "install", cwd=cwd, project_root=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".codex" / "hooks.json").exists()


def test_codex_install_is_idempotent_and_preserves_unrelated_hooks(tmp_path: Path) -> None:
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

    assert _run("codex", "install", cwd=repo).returncode == 0
    assert _run("codex", "install", cwd=repo).returncode == 0

    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["custom"] == {"keep": True}
    commands = _commands(config)
    assert "echo unrelated" in commands
    assert len([c for c in commands if "--host claude-codex" in c]) == 2


def test_claude_project_install_preserves_other_settings(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    target = repo / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"permissions": {"allow": ["Read"]}}), encoding="utf-8")

    result = _run("claude", "install", cwd=repo)

    assert result.returncode == 0, result.stderr
    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["permissions"] == {"allow": ["Read"]}
    assert len([c for c in _commands(config) if "--host claude-codex" in c]) == 2


def test_antigravity_project_install_uses_agents_hooks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    result = _run("antigravity", "install", cwd=repo)

    assert result.returncode == 0, result.stderr
    target = repo / ".agents" / "hooks.json"
    config = json.loads(target.read_text(encoding="utf-8"))
    assert "context-management" in config
    command = config["context-management"]["PreInvocation"][0]["command"]
    assert str(PROVIDER.resolve()) in command
    assert "--host antigravity" in command


def test_opencode_project_install_copies_selected_adapter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    result = _run("opencode", "install", cwd=repo, opencode_major=2)

    assert result.returncode == 0, result.stderr
    target = repo / ".opencode" / "plugins" / "context-management.ts"
    expected = SKILL_ROOT / "hooks" / "opencode" / "v2.ts"
    assert target.read_text(encoding="utf-8") == expected.read_text(encoding="utf-8")
    assert _run("opencode", "status", cwd=repo).returncode == 0


def test_status_and_remove_default_to_project(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    assert _run("codex", "status", cwd=repo).returncode == 1
    assert _run("codex", "install", cwd=repo).returncode == 0
    assert _run("codex", "status", cwd=repo).returncode == 0
    assert _run("codex", "remove", cwd=repo).returncode == 0
    assert _run("codex", "status", cwd=repo).returncode == 1


def test_tui_orders_scope_then_detected_provider_then_action(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    codex = fake_bin / ("codex.exe" if os.name == "nt" else "codex")
    codex.write_text("", encoding="utf-8")
    codex.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

    result = _run(
        "",
        "",
        cwd=repo,
        stdin="\n\n\n",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.index("1) Scope") < result.stdout.index("2) Provider")
    assert result.stdout.index("2) Provider") < result.stdout.index("3) Action")
    assert "Codex  ✓ detected / recommended" in result.stdout
    assert (repo / ".codex" / "hooks.json").exists()


def test_invalid_existing_json_fails_without_rewrite(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    target = repo / ".codex" / "hooks.json"
    target.parent.mkdir()
    original = "{not-json\n"
    target.write_text(original, encoding="utf-8")

    result = _run("codex", "install", cwd=repo)

    assert result.returncode == 2
    assert target.read_text(encoding="utf-8") == original


def test_codex_home_rejected_for_project_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    result = _run(
        "codex",
        "install",
        cwd=repo,
        codex_home=tmp_path / "home",
    )
    assert result.returncode == 2
    assert "--codex-home is only valid for Codex local/global scope" in result.stderr


def test_opencode_remove_refuses_modified_plugin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    target = repo / ".opencode" / "plugins" / "context-management.ts"
    target.parent.mkdir(parents=True)
    target.write_text("// user modified\n", encoding="utf-8")

    result = _run("opencode", "remove", cwd=repo)

    assert result.returncode == 2
    assert target.exists()
