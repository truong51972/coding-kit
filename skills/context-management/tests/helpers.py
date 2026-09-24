from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "context_ops.py"
MANAGED_BLOCK_START = "<!-- context-management:start -->"
MANAGED_BLOCK_END = "<!-- context-management:end -->"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def managed_block(
    context_index: str = "",
    *,
    startup: str = "Load only the context shard needed for the current task.",
    conventions: str = "Keep durable repository-wide conventions here.",
) -> str:
    return (
        f"{MANAGED_BLOCK_START}\n"
        "## Context Management\n\n"
        "### Startup\n\n"
        f"{startup}\n\n"
        "### Context Index\n\n"
        f"{context_index.rstrip()}\n\n"
        "### Project Working Conventions\n\n"
        f"{conventions}\n"
        f"{MANAGED_BLOCK_END}\n"
    )


def write_agents(
    repo: Path,
    context_index: str = "",
    *,
    startup: str = "Load only the context shard needed for the current task.",
    conventions: str = "Keep durable repository-wide conventions here.",
    outside_before: str = "",
    outside_after: str = "",
) -> None:
    write(
        repo / "AGENTS.md",
        "# Repository Instructions\n\n"
        f"{outside_before}"
        f"{managed_block(context_index, startup=startup, conventions=conventions)}"
        f"{outside_after}",
    )


def run_context_ops(
    repo: Path,
    command: str,
    output_format: str = "json",
    *extra_args: str,
    env: dict[str, str] | None = None,
) -> tuple[int, dict, str]:
    args = [sys.executable, str(SCRIPT), command, str(repo)]
    if command != "init":
        args.extend(["--format", output_format])
    args.extend(extra_args)
    result = subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, **env} if env else None,
    )
    data = {}
    if command != "init" and output_format == "json" and result.stdout.strip():
        data = json.loads(result.stdout)
    return result.returncode, data, result.stdout + result.stderr


def init_repo(repo: Path) -> None:
    code, _data, output = run_context_ops(repo, "init")
    assert code == 0, output
