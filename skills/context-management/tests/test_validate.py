from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import init_repo, run_context_ops, write, write_agents


class ValidateTests(unittest.TestCase):
    def test_default_initialized_layout_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            code, data, output = run_context_ops(repo, "validate")

            self.assertEqual(code, 0, output)
            self.assertEqual(data["summary"]["errors"], 0)
            self.assertEqual(data["summary"]["warnings"], 0)

    def test_missing_referenced_shard_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "- [Missing](.agents/contexts/missing.md): missing",
            )
            (repo / ".agents" / "contexts").mkdir(parents=True)

            code, data, _output = run_context_ops(repo, "validate")

            self.assertEqual(code, 2)
            self.assertEqual(data["findings"][0]["code"], "BROKEN_REFERENCE")

    def test_missing_agents_or_managed_block_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".agents" / "contexts").mkdir(parents=True)

            code, data, _output = run_context_ops(repo, "validate")

            self.assertEqual(code, 2)
            self.assertEqual(data["findings"][0]["code"], "MANAGED_BLOCK_ERROR")

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "AGENTS.md", "# Unmanaged\n")
            (repo / ".agents" / "contexts").mkdir(parents=True)

            code, data, _output = run_context_ops(repo, "validate")

            self.assertEqual(code, 2)
            self.assertEqual(data["findings"][0]["code"], "MANAGED_BLOCK_ERROR")

    def test_orphan_shard_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(repo, "- [Kept](.agents/contexts/kept.md): kept")
            write(context_dir / "kept.md", "# Kept\n")
            write(context_dir / "orphan.md", "# Orphan\n")

            code, data, _output = run_context_ops(repo, "validate")

            self.assertEqual(code, 1)
            self.assertIn(
                "ORPHAN_SHARD",
                {finding["code"] for finding in data["findings"]},
            )

    def test_shard_cannot_escape_context_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "- [Escaped](.agents/contexts/../escaped.md): escaped",
            )
            (repo / ".agents" / "contexts").mkdir(parents=True)

            code, data, _output = run_context_ops(repo, "validate")

            self.assertEqual(code, 2)
            self.assertEqual(data["findings"][0]["code"], "CONTEXT_REFERENCE_ESCAPE")

    def test_source_markdown_reference_outside_index_is_not_a_shard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): a",
                startup="Read [architecture](docs/architecture.md) when needed.",
            )
            write(context_dir / "a.md", "# A\n")
            write(repo / "docs" / "architecture.md", "# Architecture\n")

            code, data, output = run_context_ops(repo, "validate")

            self.assertEqual(code, 0, output)
            self.assertEqual(data["summary"]["errors"], 0)

    def test_custom_layout_passes_without_default_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(repo, "- [Custom](.agents/contexts/custom.md): custom")
            write(context_dir / "custom.md", "# Custom\n")

            code, data, output = run_context_ops(repo, "validate")

            self.assertEqual(code, 0, output)
            self.assertEqual(data["summary"]["errors"], 0)

    def test_duplicate_target_warns_even_with_different_link_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): first\n"
                "- [A again](a.md): duplicate",
            )
            write(context_dir / "a.md", "# A\n")

            code, data, _output = run_context_ops(repo, "validate")

            self.assertEqual(code, 1)
            self.assertIn(
                "DUPLICATE_CONTENT_WARNING",
                {finding["code"] for finding in data["findings"]},
            )

    def test_legacy_layout_files_are_errors(self) -> None:
        for legacy_name in ("index.md", "working-conventions.md"):
            with self.subTest(legacy_name=legacy_name), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                context_dir = repo / ".agents" / "contexts"
                write_agents(repo, "- [A](.agents/contexts/a.md): a")
                write(context_dir / "a.md", "# A\n")
                write(context_dir / legacy_name, "# Legacy\n")

                code, data, _output = run_context_ops(repo, "validate")

                self.assertEqual(code, 2)
                self.assertIn(
                    "LEGACY_LAYOUT_ERROR",
                    {finding["code"] for finding in data["findings"]},
                )


if __name__ == "__main__":
    unittest.main()
