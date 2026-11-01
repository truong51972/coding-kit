"""Regression tests for experience catalog, verified capture, and passive hooks."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
from experience_ops import catalog, parse  # noqa: E402
from failure_guard import handle_hook, observe  # noqa: E402


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "AGENTS.md").write_text("# Test repository\n", encoding="utf-8")
        patcher = patch.dict(os.environ, {
            "AGENTS_HOME": str(self.tmp / "home"),
            "XDG_STATE_HOME": str(self.tmp / "state"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "experience_ops.py"),
             "--repo", str(self.repo), *args],
            text=True, capture_output=True, check=False, env=os.environ.copy())

    def capture(self, name="pytest-wrong-interpreter", *extra):
        return self.cli(
            "capture", "--name", name,
            "--description", "Pytest import failures caused by interpreter mismatch",
            "--symptoms", "ModuleNotFoundError when running tests",
            "--failed-approach", "Reinstalling deps repeatedly",
            "--root-cause", "Test runner used a different environment",
            "--resolution", "Select the project interpreter and re-run tests",
            "--applicability", "Only after validating interpreter mismatch",
            "--evidence", "Relevant tests passed in the correct environment",
            "--tags", "python,pytest,environment", "--verified", *extra)

    def test_capture_list_show_lint_retire(self):
        created = self.capture()
        self.assertEqual(created.returncode, 0, created.stderr)
        path = self.repo / ".agents/experiences/pytest-wrong-interpreter.md"
        self.assertTrue(path.exists())
        self.assertEqual(parse(path)["name"], "pytest-wrong-interpreter")
        listed = self.cli("list", "--query", "pytest")
        self.assertEqual(listed.returncode, 0)
        self.assertIn("pytest-wrong-interpreter:", listed.stdout)
        self.assertNotIn("Reinstalling deps", listed.stdout)
        shown = self.cli("show", "pytest-wrong-interpreter")
        self.assertIn("## Root Cause", shown.stdout)
        self.assertIn("Reinstalling deps", shown.stdout)
        self.assertEqual(self.cli("lint").returncode, 0)
        retired = self.cli("retire", "pytest-wrong-interpreter")
        self.assertEqual(retired.returncode, 0)
        self.assertNotIn("pytest-wrong-interpreter", self.cli("list").stdout)
        self.assertEqual(self.cli("show", "pytest-wrong-interpreter").returncode, 2)

    def test_refuses_automatic_or_duplicate_capture(self):
        self.assertEqual(self.capture().returncode, 0)
        again = self.capture()
        self.assertEqual(again.returncode, 2)
        self.assertIn("already exists", again.stderr)
        unverified = self.cli("capture", "--name", "other", "--description", "Other",
            "--symptoms", "X", "--failed-approach", "X", "--root-cause", "X",
            "--resolution", "X", "--applicability", "X", "--evidence", "X")
        self.assertEqual(unverified.returncode, 2)
        self.assertIn("--verified", unverified.stderr)

    def test_global_and_project_precedence(self):
        self.assertEqual(self.capture("--scope", "global").returncode, 0)
        self.assertEqual(self.capture().returncode, 0)
        global_path = self.tmp / "home/experiences/pytest-wrong-interpreter.md"
        self.assertTrue(global_path.is_file())
        result = self.cli("list", "--json")
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 1)
        self.assertIn(str(self.repo), data[0]["path"])
        self.cli("retire", "pytest-wrong-interpreter", "--scope", "project")
        self.assertEqual(json.loads(self.cli("list", "--json").stdout), [])

    def test_lint_rejects_invalid_or_oversized_record(self):
        self.assertEqual(self.capture().returncode, 0)
        path = self.repo / ".agents/experiences/pytest-wrong-interpreter.md"
        path.write_text(path.read_text().replace("status: active", "status: pending"))
        self.assertEqual(self.cli("lint").returncode, 2)
        self.assertEqual(self.cli("list").returncode, 0)  # graceful per-entry skip

    def test_query_filters_and_limits(self):
        self.assertEqual(self.capture().returncode, 0)
        self.assertEqual(self.cli("list", "--query", "docker").stdout, "")
        self.assertEqual(self.cli("list", "--limit", "0").returncode, 2)

    def test_loop_guard_alert_once_and_reset_on_success(self):
        output = "Traceback (most recent call last):\nModuleNotFoundError: sample\n"
        for attempt in range(2):
            self.assertIsNone(observe(session="worker-a", repo=str(self.repo),
                                      command="uv run pytest", exit_code=1, output=output))
        warning = observe(session="worker-a", repo=str(self.repo),
                          command="uv run pytest", exit_code=1, output=output)
        self.assertIn("Potential failure loop", warning)
        self.assertIsNone(observe(session="worker-a", repo=str(self.repo),
                                  command="uv run pytest", exit_code=1, output=output))
        self.assertIsNone(observe(session="worker-b", repo=str(self.repo),
                                  command="uv run pytest", exit_code=1, output=output))
        observe(session="worker-a", repo=str(self.repo),
                command="uv run pytest", exit_code=0, output="ok")
        self.assertIsNone(observe(session="worker-a", repo=str(self.repo),
                                  command="uv run pytest", exit_code=1, output=output))
        state_files = list((self.tmp / "state/coding-kit/experience-guard").glob("*.json"))
        self.assertEqual(len(state_files), 2)
        self.assertNotIn("ModuleNotFoundError", state_files[0].read_text())

    def test_improving_test_failures_reset_streak(self):
        for count in (5, 4, 3):
            warning = observe(session="worker", repo=str(self.repo),
                  command="pytest", exit_code=1, output=f"=== {count} failed ===")
            self.assertIsNone(warning)
        self.assertIsNone(observe(session="worker", repo=str(self.repo),
                                  command="pytest", exit_code=1, output="=== 3 failed ==="))
        warning = observe(session="worker", repo=str(self.repo),
                          command="pytest", exit_code=1, output="=== 3 failed ===")
        self.assertIn("Potential failure loop", warning)

    def test_unsupported_hooks_and_unknown_status_are_safe(self):
        self.assertIsNone(handle_hook({"hook_event_name": "PreToolUse",
                                      "tool_name": "Bash"}))
        self.assertIsNone(handle_hook({
            "hook_event_name": "PostToolUse", "tool_name": "Bash",
            "session_id": "s", "tool_input": {"command": "pytest"},
            "tool_response": "ModuleNotFoundError: sample"}))
        for i in range(3):
            result = handle_hook({
                "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
                "session_id": "s", "cwd": str(self.repo),
                "tool_input": {"command": "pytest"},
                "tool_response": {"stderr": "ModuleNotFoundError: sample"}})
        self.assertIn("additionalContext", result["hookSpecificOutput"])

    def test_session_start_only_metadata(self):
        self.assertEqual(self.capture().returncode, 0)
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("experience_provider",
                                       SKILL / "hooks/experience_provider.py")
        provider = module_from_spec(spec)
        spec.loader.exec_module(provider)
        output = provider.handle({"hook_event_name": "SessionStart", "cwd": str(self.repo)})
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pytest-wrong-interpreter:", text)
        self.assertNotIn("Reinstalling deps", text)
        self.assertEqual(provider.handle({"hook_event_name": "SessionStart",
                                          "cwd": str(self.tmp / "empty")}), output
                         if False else None)  # no repo- or personal-level lessons there


if __name__ == "__main__":
    unittest.main()
