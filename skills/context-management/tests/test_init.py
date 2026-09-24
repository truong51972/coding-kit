from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import (
    MANAGED_BLOCK_END,
    MANAGED_BLOCK_START,
    run_context_ops,
    write,
)


class InitTests(unittest.TestCase):
    def test_init_creates_agents_and_new_default_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo" / "nested"

            code, _data, output = run_context_ops(repo, "init")

            self.assertEqual(code, 0, output)
            agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(agents.count(MANAGED_BLOCK_START), 1)
            self.assertEqual(agents.count(MANAGED_BLOCK_END), 1)
            self.assertIn("### Context Index", agents)
            context_dir = repo / ".agents" / "contexts"
            for name in (
                "source-priority.md",
                "project-baseline.md",
                "active-assumptions.md",
            ):
                self.assertTrue((context_dir / name).exists(), name)
            self.assertFalse((context_dir / "index.md").exists())
            self.assertFalse((context_dir / "working-conventions.md").exists())

    def test_init_inserts_after_h1_and_preserves_surrounding_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            prefix = "# Existing Instructions\n"
            suffix = "\nExact body bytes.\n\n## Existing Section\n\nKeep  trailing spaces.  \n"
            original = prefix + suffix
            write(repo / "AGENTS.md", original)

            code, _data, output = run_context_ops(repo, "init")

            self.assertEqual(code, 0, output)
            result = (repo / "AGENTS.md").read_text(encoding="utf-8")
            start = result.index(MANAGED_BLOCK_START)
            end = result.index(MANAGED_BLOCK_END) + len(MANAGED_BLOCK_END)
            self.assertEqual(result[:start], prefix + "\n")
            self.assertEqual(result[end : end + 1], "\n")
            self.assertEqual(result[end + 1 :], suffix)

    def test_repeated_init_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            code, _data, output = run_context_ops(repo, "init")
            self.assertEqual(code, 0, output)
            agents = repo / "AGENTS.md"
            original = agents.read_bytes()

            code, _data, output = run_context_ops(repo, "init")

            self.assertEqual(code, 0, output)
            self.assertEqual(agents.read_bytes(), original)
            self.assertEqual(original.count(MANAGED_BLOCK_START.encode()), 1)

    def test_init_does_not_overwrite_custom_shards_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            custom = repo / ".agents" / "contexts" / "source-priority.md"
            write(custom, "# Custom source priority\n")
            write(repo / ".agents" / "contexts" / "custom.md", "# Custom shard\n")

            code, _data, output = run_context_ops(repo, "init")

            self.assertEqual(code, 0, output)
            self.assertEqual(custom.read_text(encoding="utf-8"), "# Custom source priority\n")
            self.assertTrue((repo / ".agents" / "contexts" / "custom.md").exists())

    def test_overwrite_refuses_modified_shards_and_preserves_all_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            code, _data, output = run_context_ops(repo, "init")
            self.assertEqual(code, 0, output)
            agents = repo / "AGENTS.md"
            developed = agents.read_text(encoding="utf-8").replace(
                "Keep secrets and credentials",
                "Keep developed conventions and credentials",
            )
            write(agents, developed)
            custom = repo / ".agents" / "contexts" / "source-priority.md"
            write(custom, "# Keep me\n")
            baseline = repo / ".agents" / "contexts" / "project-baseline.md"
            baseline_before = baseline.read_bytes()

            code, _data, output = run_context_ops(
                repo,
                "init",
                "json",
                "--overwrite",
            )

            self.assertEqual(code, 2, output)
            self.assertIn("refusing to overwrite modified context shard", output)
            self.assertEqual(agents.read_text(encoding="utf-8"), developed)
            self.assertEqual(custom.read_text(encoding="utf-8"), "# Keep me\n")
            self.assertEqual(baseline.read_bytes(), baseline_before)

    def test_overwrite_is_idempotent_when_existing_shards_match_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            code, _data, output = run_context_ops(repo, "init")
            self.assertEqual(code, 0, output)
            before = {
                path.name: path.read_bytes()
                for path in (repo / ".agents" / "contexts").glob("*.md")
            }

            code, _data, output = run_context_ops(
                repo,
                "init",
                "json",
                "--overwrite",
            )

            self.assertEqual(code, 0, output)
            after = {
                path.name: path.read_bytes()
                for path in (repo / ".agents" / "contexts").glob("*.md")
            }
            self.assertEqual(after, before)

    def test_malformed_or_duplicate_markers_fail_without_partial_writes(self) -> None:
        malformed = (
            f"# Repo\n\n{MANAGED_BLOCK_START}\n## Context Management\n",
            (
                "# Repo\n\n"
                f"{MANAGED_BLOCK_START}\n## Context Management\n{MANAGED_BLOCK_END}\n"
                f"{MANAGED_BLOCK_START}\n## Context Management\n{MANAGED_BLOCK_END}\n"
            ),
            (
                "# Repo\n\n"
                f"{MANAGED_BLOCK_END}\n## Context Management\n{MANAGED_BLOCK_START}\n"
            ),
        )
        for content in malformed:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                agents = repo / "AGENTS.md"
                write(agents, content)
                original = agents.read_bytes()

                code, _data, _output = run_context_ops(repo, "init")

                self.assertEqual(code, 2)
                self.assertEqual(agents.read_bytes(), original)
                self.assertFalse((repo / ".agents" / "contexts").exists())

    def test_legacy_layout_fails_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            original = "# Existing\n\nUnmanaged body.\n"
            write(repo / "AGENTS.md", original)
            legacy = repo / ".agents" / "contexts" / "index.md"
            write(legacy, "# Legacy index\n")

            code, _data, output = run_context_ops(repo, "init")

            self.assertEqual(code, 2, output)
            self.assertEqual(
                (repo / "AGENTS.md").read_text(encoding="utf-8"),
                original,
            )
            self.assertEqual(legacy.read_text(encoding="utf-8"), "# Legacy index\n")
            self.assertFalse(
                (repo / ".agents" / "contexts" / "project-baseline.md").exists()
            )


if __name__ == "__main__":
    unittest.main()
