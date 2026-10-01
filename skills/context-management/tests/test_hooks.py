from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HOOK_SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "context_provider.py"
START = "<!-- context-management:start -->"
END = "<!-- context-management:end -->"


def _managed_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "AGENTS.md").write_text(
        f"# Repo\n\n{START}\n## Context Management\n{END}\n",
        encoding="utf-8",
    )
    return path


def _run(host: str, payload: dict, cwd: Path) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), "--host", host],
        cwd=cwd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else None


def test_claude_codex_is_silent_without_managed_marker(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Repo\n", encoding="utf-8")
    output = _run(
        "claude-codex",
        {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(tmp_path)},
        tmp_path,
    )
    assert output is None


def test_claude_codex_bootstraps_from_nested_cwd(tmp_path: Path) -> None:
    repo = _managed_repo(tmp_path / "repo")
    nested = repo / "apps" / "api"
    nested.mkdir(parents=True)
    output = _run(
        "claude-codex",
        {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(nested)},
        nested,
    )
    text = output["hookSpecificOutput"]["additionalContext"]
    assert "Context Management is active" in text
    assert "lazy-load only the shard needed next" in text
    assert ".agents/contexts" not in text


def test_compact_session_gets_continuity_not_full_context(tmp_path: Path) -> None:
    repo = _managed_repo(tmp_path / "repo")
    output = _run(
        "claude-codex",
        {"hook_event_name": "SessionStart", "source": "compact", "cwd": str(repo)},
        repo,
    )
    text = output["hookSpecificOutput"]["additionalContext"]
    assert "after compaction" in text
    assert "do not bulk-load context" in text


def test_subagent_gets_non_inheritance_reminder(tmp_path: Path) -> None:
    repo = _managed_repo(tmp_path / "repo")
    output = _run(
        "claude-codex",
        {"hook_event_name": "SubagentStart", "cwd": str(repo)},
        repo,
    )
    text = output["hookSpecificOutput"]["additionalContext"]
    assert "Do not assume parent-loaded shards were inherited" in text


def test_antigravity_injects_only_on_first_invocation(tmp_path: Path) -> None:
    repo = _managed_repo(tmp_path / "repo")
    first = _run(
        "antigravity",
        {"invocationNum": 0, "workspacePaths": [str(repo)]},
        repo,
    )
    later = _run(
        "antigravity",
        {"invocationNum": 4, "workspacePaths": [str(repo)]},
        repo,
    )
    assert "Context Management is active" in first["injectSteps"][0]["ephemeralMessage"]
    assert later == {}
