from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import init_repo, run_context_ops, write, write_agents


class AuditTests(unittest.TestCase):
    def test_lazy_loading_violations_warn_and_conditional_loading_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "- [Source](.agents/contexts/source-priority.md): source",
                startup=(
                    "Always read `source-priority.md` before every task.\n"
                    "Read all context files first."
                ),
            )
            write(
                repo / ".agents" / "contexts" / "source-priority.md",
                "# Source\n",
            )

            code, data, _output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0)
            codes = [finding["code"] for finding in data["findings"]]
            self.assertGreaterEqual(codes.count("LAZY_LOADING_WARNING"), 2)

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "- [Source](.agents/contexts/source-priority.md): source",
                startup="Read `source-priority.md` only when source ownership matters.",
            )
            write(
                repo / ".agents" / "contexts" / "source-priority.md",
                "# Source\n",
            )

            code, data, output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0, output)
            self.assertEqual(data["summary"]["warnings"], 0)

    def test_missing_source_path_in_managed_content_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "apps").mkdir()
            write_agents(
                repo,
                "",
                conventions=(
                    "Missing `apps/missing.py`, URL `https://example.com/x.md`, "
                    "command `python3`."
                ),
            )
            (repo / ".agents" / "contexts").mkdir(parents=True)

            code, data, _output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0)
            findings = data["findings"]
            self.assertEqual(
                len([f for f in findings if f["code"] == "MISSING_SOURCE_PATH"]),
                1,
            )

    def test_oversized_managed_block_and_shard_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(
                repo,
                "- [Big](.agents/contexts/big.md): big\n"
                "- [Medium](.agents/contexts/medium.md): medium",
                conventions="x" * 4100,
            )
            write(context_dir / "big.md", "y" * 16050)
            write(context_dir / "medium.md", "z" * 10000)

            code, data, _output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0)
            size_findings = [
                finding
                for finding in data["findings"]
                if finding["code"] == "SHARD_SIZE_WARNING"
            ]
            self.assertGreaterEqual(len(size_findings), 2)
            size_files = {finding["file"] for finding in size_findings}
            self.assertIn("AGENTS.md", size_files)
            self.assertIn(".agents/contexts/big.md", size_files)
            self.assertNotIn(".agents/contexts/medium.md", size_files)
            self.assertNotIn(
                "TOTAL_SIZE_WARNING",
                {f["code"] for f in data["findings"]},
            )

    def test_duplicate_content_and_orphan_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            duplicate = (
                "This durable context sentence is intentionally long enough "
                "to be duplicated exactly.\n"
            )
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): a\n"
                "- [B](.agents/contexts/b.md): b",
            )
            write(context_dir / "a.md", duplicate)
            write(context_dir / "b.md", duplicate)
            write(context_dir / "orphan.md", "# Orphan\n")

            code, data, _output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0)
            codes = {finding["code"] for finding in data["findings"]}
            self.assertIn("DUPLICATE_CONTENT_WARNING", codes)
            self.assertIn("ORPHAN_SHARD", codes)

    def test_json_schema_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)

            code, data, output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0, output)
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["command"], "audit")
            self.assertEqual(
                data["semantic_source_verification"]["status"],
                "not_performed",
            )

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(repo, "", conventions="TODO")
            (repo / ".agents" / "contexts").mkdir(parents=True)
            code, data, _output = run_context_ops(repo, "audit")
            self.assertEqual(code, 0)
            self.assertEqual(data["summary"]["warnings"], 1)

            strict_code, strict_data, _output = run_context_ops(
                repo,
                "audit",
                "json",
                "--strict",
            )
            self.assertEqual(strict_code, 1)
            self.assertEqual(strict_data.keys(), data.keys())

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            code, _data, _output = run_context_ops(repo, "audit")
            self.assertEqual(code, 2)

    def test_eager_task_bundle_warns_but_single_shard_route_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): a\n"
                "- [B](.agents/contexts/b.md): b",
                startup=(
                    "For backend work, load [A](.agents/contexts/a.md) and "
                    "[B](.agents/contexts/b.md).\n"
                    "For docs work, load only [A](.agents/contexts/a.md)."
                ),
            )
            write(context_dir / "a.md", "# A\n")
            write(context_dir / "b.md", "# B\n")

            code, data, output = run_context_ops(repo, "audit")

            self.assertEqual(code, 0, output)
            eager = [
                f
                for f in data["findings"]
                if f["code"] == "EAGER_SHARD_BUNDLE"
            ]
            self.assertEqual(len(eager), 1)
            self.assertEqual(
                eager[0]["details"]["references"],
                [".agents/contexts/a.md", ".agents/contexts/b.md"],
            )

    def test_section_identifier_density_exempts_routing_content(self) -> None:
        exact = " ".join(f"`service_{i}`" for i in range(12))
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write_agents(
                repo,
                "- [Detail](.agents/contexts/detail.md): detail",
            )
            write(context_dir / "detail.md", f"# Baseline\n\n{exact}\n")

            _code, data, _output = run_context_ops(repo, "audit")
            dense = [
                f
                for f in data["findings"]
                if f["code"] == "POSSIBLE_SOURCE_DETAIL_DUPLICATION"
            ]
            self.assertEqual(len(dense), 1)

            write(
                context_dir / "detail.md",
                "# Baseline\n\nDurable architecture boundary.\n",
            )
            write(context_dir / "source-priority.md", f"# Routes\n\n{exact}\n")
            write_agents(
                repo,
                "- [Detail](.agents/contexts/detail.md): detail\n"
                "- [Source](.agents/contexts/source-priority.md): routes",
                conventions=exact,
            )
            _code, data, _output = run_context_ops(repo, "audit")
            dense = [
                f
                for f in data["findings"]
                if f["code"] == "POSSIBLE_SOURCE_DETAIL_DUPLICATION"
            ]
            self.assertEqual(dense, [])

    def test_local_markdown_links_resolve_from_containing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            context_dir = repo / ".agents" / "contexts"
            write(repo / "docs" / "architecture.md", "# Architecture\n")
            write_agents(
                repo,
                "- [Detail](.agents/contexts/detail.md): detail",
            )
            write(
                context_dir / "detail.md",
                "[Broken source](docs/architecture.md) and "
                "[valid source](../../docs/architecture.md).\n",
            )

            _code, data, _output = run_context_ops(repo, "audit")
            broken = [
                f
                for f in data["findings"]
                if f["code"] == "LOCAL_LINK_TARGET_MISSING"
            ]
            self.assertEqual(len(broken), 1)
            self.assertEqual(
                broken[0]["details"]["target"],
                "docs/architecture.md",
            )

    def test_generic_agent_runtime_guidance_warns_only_in_managed_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "",
                conventions=(
                    "Network access is restricted. Never delete untracked files."
                ),
                outside_after="\nSandbox guidance outside the managed block.\n",
            )
            (repo / ".agents" / "contexts").mkdir(parents=True)

            _code, data, _output = run_context_ops(repo, "audit")
            generic = [
                f
                for f in data["findings"]
                if f["code"] == "GENERIC_AGENT_RULE"
            ]
            self.assertEqual(len(generic), 1)

    def test_git_commit_and_dirty_mtime_are_drift_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo,
                check=True,
            )
            write(repo / "source.txt", "committed\n")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "source"],
                cwd=repo,
                check=True,
            )
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): a",
            )
            context = repo / ".agents" / "contexts" / "a.md"
            write(context, "# A\n")
            old = 1_000_000_000
            os.utime(context, (old, old))
            os.utime(repo / "AGENTS.md", (old, old))
            write(repo / "source.txt", "dirty\n")

            _code, data, _output = run_context_ops(repo, "audit")
            drift = [
                f
                for f in data["findings"]
                if f["code"] == "SOURCE_CHANGED_SINCE_CONTEXT"
            ]
            self.assertEqual(len(drift), 1)
            self.assertTrue(drift[0]["details"]["newer_commits"])
            self.assertEqual(
                drift[0]["details"]["newer_dirty_tracked_files"],
                ["source.txt"],
            )
            self.assertEqual(
                drift[0]["details"]["semantic_verification"],
                "not_performed",
            )

    def test_drift_is_reported_per_shard_so_fresh_context_does_not_mask_stale_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo,
                check=True,
            )
            write(repo / "source.txt", "committed\n")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-qm", "source"],
                cwd=repo,
                check=True,
            )
            write_agents(
                repo,
                "- [Stale](.agents/contexts/stale.md): stale\n"
                "- [Fresh](.agents/contexts/fresh.md): fresh",
            )
            stale = repo / ".agents" / "contexts" / "stale.md"
            fresh = repo / ".agents" / "contexts" / "fresh.md"
            write(stale, "# Stale\n")
            write(fresh, "# Fresh\n")
            old = 1_000_000_000
            future = 4_000_000_000
            os.utime(stale, (old, old))
            os.utime(fresh, (future, future))
            os.utime(repo / "AGENTS.md", (future, future))

            _code, data, _output = run_context_ops(repo, "audit")
            drift = [
                f
                for f in data["findings"]
                if f["code"] == "SOURCE_CHANGED_SINCE_CONTEXT"
            ]

            self.assertEqual(len(drift), 1)
            self.assertEqual(drift[0]["file"], ".agents/contexts/stale.md")
            self.assertTrue(drift[0]["details"]["newer_commits"])

    def test_git_unavailable_is_info_and_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): a",
            )
            write(repo / ".agents" / "contexts" / "a.md", "# A\n")

            code, data, output = run_context_ops(
                repo,
                "audit",
                env={"PATH": "/nonexistent"},
            )

            self.assertEqual(code, 0, output)
            info = [
                f for f in data["findings"] if f["code"] == "GIT_UNAVAILABLE"
            ]
            self.assertEqual(len(info), 1)
            self.assertEqual(info[0]["severity"], "info")

    def test_status_counts_managed_block_and_shards_not_outside_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_agents(
                repo,
                "- [A](.agents/contexts/a.md): a",
                outside_after="\n" + ("outside " * 5000),
            )
            write(repo / ".agents" / "contexts" / "a.md", "# A\n")

            code, data, output = run_context_ops(repo, "status")

            self.assertEqual(code, 0, output)
            summaries = [
                finding
                for finding in data["findings"]
                if finding["code"] == "CONTEXT_STATUS_SUMMARY"
            ]
            agents_summary = next(
                finding for finding in summaries if finding["file"] == "AGENTS.md"
            )
            self.assertLess(
                agents_summary["details"]["estimated_tokens"],
                500,
            )
            total = next(
                finding
                for finding in summaries
                if finding["file"] == ".agents/contexts"
            )
            self.assertEqual(total["details"]["files"], 2)


if __name__ == "__main__":
    unittest.main()
