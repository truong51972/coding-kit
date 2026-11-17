"""Assumption ledger CLI regression tests: explicit storage, no false promotion."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/assumption_ops.py"
CONTEXT_OPS = Path(__file__).resolve().parents[1] / "scripts/context_ops.py"


def _run(repo: Path, *argv: str):
    return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), *argv],
                          cwd=repo, text=True, capture_output=True, check=False)


def _capture(repo: Path, **updates: str):
    values = dict(claim="Worker runs as a single instance",
                  scope="evaluation-worker / prod",
                  decision="idempotent retry design",
                  basis="inferred from local compose config",
                  verify_by="inspect actual deployment replicas",
                  owner="coordinator")
    values.update(updates)
    flags = [f"--{key.replace('_', '-')}" for key in values]
    args = [value for key in values for value in (f"--{key.replace('_', '-')}", values[key])]
    return _run(repo, "capture", *args)


def test_no_ledger_without_explicit_init(tmp_path: Path) -> None:
    root = tmp_path
    assert _run(root, "list").returncode == 2
    assert not (root / ".agents/assumptions").exists()
    result = _run(root, "init")
    assert result.returncode == 0, result.stderr
    assert _run(root, "init").returncode == 0
    assert _run(root, "lint").returncode == 0


def test_capture_idempotency_and_scope_aware_dedup(tmp_path: Path) -> None:
    root = tmp_path
    assert _run(root, "init").returncode == 0
    first = _capture(root)
    assert first.returncode == 0, first.stderr
    assert "ASM-001" in first.stdout
    duplicate = _capture(root)
    assert duplicate.returncode == 0 and "existing: ASM-001" in duplicate.stdout
    other_scope = _capture(root, scope="worker / staging")
    assert other_scope.returncode == 0, other_scope.stderr
    assert "ASM-002" in other_scope.stdout
    listed = _run(root, "list", "--query", "evaluation")
    assert "ASM-001" in listed.stdout and "ASM-002" not in listed.stdout
    assert _run(root, "lint").returncode == 0


def test_verification_requires_evidence_and_does_not_auto_promote(tmp_path: Path) -> None:
    root = tmp_path
    _run(root, "init")
    _capture(root)
    assert _run(root, "resolve", "ASM-001", "--status", "verified").returncode == 2
    resolved = _run(root, "resolve", "ASM-001", "--status", "verified",
                    "--evidence", "deployment config @ rev123")
    assert resolved.returncode == 0, resolved.stderr
    record = _run(root, "show", "ASM-001")
    assert "[x] ASM-001" in record.stdout
    assert "Status: verified" in record.stdout
    assert "Evidence: deployment config @ rev123" in record.stdout
    assert _run(root, "lint").returncode == 0
    # Verification is scoped to the ledger; no context fact is silently generated.
    assert not (root / ".agents/contexts").exists()
    again = _run(root, "resolve", "ASM-001", "--status", "verified",
                 "--evidence", "deployment config @ rev123")
    assert again.returncode == 0 and "unchanged" in again.stdout
    assert _run(root, "resolve", "ASM-001", "--status", "rejected",
                "--evidence", "conflict").returncode == 2


def test_rejected_and_retired_preserve_canonical_record(tmp_path: Path) -> None:
    root = tmp_path
    _run(root, "init")
    _capture(root)
    r = _run(root, "resolve", "ASM-001", "--status", "rejected",
             "--evidence", "production replicas=3", "--successor", "rework concurrency")
    assert r.returncode == 0, r.stderr
    assert "Successor: rework concurrency" in _run(root, "show", "ASM-001").stdout
    assert _run(root, "lint").returncode == 0


def test_rejects_unsafe_paths_and_missing_fields(tmp_path: Path) -> None:
    root = tmp_path
    assert _run(root, "--ledger", ".agents/contexts/project-baseline.md",
                "init").returncode == 2
    assert _run(root, "--ledger", "../outside.md", "init").returncode == 2
    assert _run(root, "init").returncode == 0
    assert _capture(root, basis="unsourced\ninjected content").returncode == 2
    assert _run(root, "lint").returncode == 0


def test_context_init_and_ledger_init_are_separate(tmp_path: Path) -> None:
    root = tmp_path
    (root / "AGENTS.md").write_text("# Repository\n", encoding="utf-8")
    run = subprocess.run([sys.executable, str(CONTEXT_OPS), "init", str(root)],
                         cwd=root, text=True, capture_output=True, check=False)
    assert run.returncode == 0, run.stderr
    assert not (root / ".agents/assumptions").exists()
