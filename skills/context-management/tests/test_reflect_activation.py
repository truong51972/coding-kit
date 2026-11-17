"""Regression checks for safe reflection activation and optional storage.

These tests use stdlib unittest so README's discover command executes them.
No host-specific continuation or semantic reflection is claimed here.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
PROVIDER = SKILL / "hooks" / "context_provider.py"
CONTEXT_OPS = SKILL / "scripts" / "context_ops.py"
START = "<!-- context-management:start -->"
END = "<!-- context-management:end -->"


class ReflectionActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()

    def marker(self, text: str) -> None:
        (self.repo / "AGENTS.md").write_text(text, encoding="utf-8")

    def invoke(self, host: str, extra: dict | None = None) -> dict | None:
        payload = {"cwd": str(self.repo), "workspacePaths": [str(self.repo)]}
        if host == "claude-codex":
            payload.update({"hook_event_name": "SessionStart", "source": "startup"})
        else:
            payload["invocationNum"] = 0
        if extra:
            payload.update(extra)
        run = subprocess.run(
            [sys.executable, str(PROVIDER), "--host", host],
            cwd=self.repo,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout) if run.stdout.strip() else None

    def test_exactly_one_ordered_marker_pair_activates(self) -> None:
        self.marker(f"# Repo\n{START}\n## Context Management\n### Startup\n### Context Index\n### Project Working Conventions\n{END}\n")
        result = self.invoke("claude-codex")
        self.assertIn(
            "Context Management is active",
            result["hookSpecificOutput"]["additionalContext"],
        )

    def test_duplicate_marker_pairs_do_not_activate_any_host(self) -> None:
        self.marker(f"# Repo\n{START}\n## Context Management\n### Startup\n### Context Index\n### Project Working Conventions\n{END}\n"
                    f"{START}\n## Context Management\n{END}\n")
        self.assertIsNone(self.invoke("claude-codex"))
        self.assertEqual(self.invoke("antigravity"), {})

    def test_unbalanced_markers_do_not_activate(self) -> None:
        for text in (
            f"# Repo\n{START}\n{START}\n{END}\n",
            f"# Repo\n{START}\n{END}\n{END}\n",
        ):
            with self.subTest(text=text):
                self.marker(text)
                self.assertIsNone(self.invoke("claude-codex"))

    def test_reversed_markers_do_not_activate(self) -> None:
        self.marker(f"# Repo\n{END}\n{START}\n")
        self.assertIsNone(self.invoke("claude-codex"))

    def test_init_does_not_create_optional_assumption_ledger(self) -> None:
        self.marker("# Repo\n")
        run = subprocess.run(
            [sys.executable, str(CONTEXT_OPS), "init", str(self.repo)],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue((self.repo / ".agents/contexts/active-assumptions.md").is_file())
        self.assertFalse((self.repo / ".agents/assumptions").exists())


if __name__ == "__main__":
    unittest.main()
