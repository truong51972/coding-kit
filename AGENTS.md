# Engineering agent instructions

## Purpose and precedence

This file defines universal engineering principles and execution policy.
Repository-specific architecture, commands, boundaries, and validation belong
in the repository's `AGENTS.md` or a more specific nested instruction file.

The closest applicable instruction takes precedence. Repository code,
configuration, tests, CI, framework conventions, and documentation remain the
source of truth.

When authoritative artifacts disagree, resolve ownership from repository
conventions and the boundary that owns the behavior. Do not use recency alone
as evidence of authority. Keep unresolved conflicts visible rather than
guessing.

## Engineering principles

### Establish the real requirement

Do not implement a feature merely because it is technically possible.

Before a non-trivial behavioral change, establish enough evidence to understand:

- the concrete user, operational, or business need;
- the current behavior and why it is absent, incorrect, or insufficient;
- the required outcome and relevant acceptance criteria;
- the scope and boundaries that must remain unchanged.

Treat the requested solution as a hypothesis. Investigate the problem and the
existing execution path before committing to an implementation.

Clarify ambiguity that could materially affect contracts, persisted data,
security, architecture, or user-visible behavior. For low-risk ambiguity, state
the assumption, choose the simplest reversible option, and proceed.

### Prefer the simplest sufficient solution

Consider simpler options before adding new code or infrastructure:

1. Remove the need or use existing behavior or configuration.
2. Reuse an established repository implementation or pattern.
3. Prefer native framework or platform capabilities.
4. Prefer the standard library or already-installed dependencies when they
   reduce net complexity.
5. Add a mature dependency only when justified.
6. Write custom infrastructure only when simpler options do not satisfy the
   requirement.

Choose by ownership, correctness, maintainability, and net complexity rather
than mechanically following the list.

Prefer deletion over addition, explicit code over premature abstraction, boring
code over clever code, the smallest coherent diff, and root-cause fixes over
symptom patches.

Reuse proven abstractions, but do not create one solely because code might be
reused later. A small amount of local duplication is preferable to a premature
shared abstraction with unclear ownership or unstable requirements.

Every new abstraction, wrapper, interface, service, configuration layer,
dependency, cache, feature flag, or infrastructure component must solve a
current problem and reduce net system complexity. A single implementation,
caller, or use case is evidence against abstraction unless a concrete boundary
requires it.

YAGNI applies to speculative capabilities, not to correctness, clarity,
testability, security, or maintaining an established boundary.

### Respect authoritative boundaries

Enforce invariants at the lowest authoritative boundary that owns them:

- database constraints for persisted-data invariants;
- type or schema contracts for structural invariants;
- framework or platform lifecycle for native behavior;
- application code only when lower boundaries cannot express the rule.

Do not reimplement behavior already owned by a framework, platform, database,
generator, or repository tool.

Preserve established public contracts and persisted-data compatibility unless
the requested change explicitly requires breaking them. Do not add speculative
compatibility layers for undocumented or hypothetical consumers.

### Protect generated artifacts

Identify generated or tool-managed artifacts through framework conventions,
generated headers, documentation, configuration, and existing commands.

Modify the authoritative source and use the canonical generator, CLI, migration
command, formatter, compiler, package manager, or repository script when the
tool owns the artifact.

Hand-author or edit a generated artifact only when the owning framework or tool
explicitly supports it and the required semantics cannot be expressed through
the normal generator path. Inspect and validate generated output rather than
assuming successful generation proves correctness.

### Keep changes coherent and scoped

Prefer one self-contained behavioral change per diff. Keep required production
code and directly related tests together, but separate unrelated refactoring,
formatting, dependency upgrades, file movement, and cleanup.

Do not introduce abstractions, compatibility layers, versioning, configuration,
or infrastructure for hypothetical future requirements.

Leave affected code no harder to understand, test, operate, or change than
before, without expanding the task into general cleanup or theoretical
perfection.

## Workspace and mutation safety

Review, analysis, investigation, and planning requests are read-only unless the
user also requests implementation. Do not modify repository state merely because
a possible fix was identified.

Before editing, inspect the working tree and identify pre-existing changes.
Do not discard, overwrite, revert, reformat, or include unrelated user changes.
Do not run destructive Git, filesystem, database, or migration commands without
explicit authorization.

Do not commit, log, copy into fixtures, or expose credentials, tokens, private
keys, or other secrets. Preserve the repository's existing secret-management
boundary.

Only one write-capable agent may modify overlapping files at a time. Parallel
writers are acceptable only when file ownership and relevant contracts are
independent and each writer uses an isolated worktree, branch, or equivalent
workspace.

## Execution model

### Single-agent by default

The primary agent handles localized work directly: inspection, implementation,
tests, validation, and review. Do not spawn subagents merely because they are
available.

### Workflow selection

Use a trivial workflow for typo-only, comment-only, mechanical formatting,
narrow documentation, and obvious non-behavioral configuration changes.

Use a standard workflow for localized, well-understood changes with clear
ownership and acceptance criteria. Delegate bounded work only when
specialization, independent exploration, testing, or fresh-context review
materially improves confidence.

Use a planning-first workflow for substantial, cross-boundary, or high-risk
changes. Investigate the current execution path and produce a concrete
implementation plan before editing unless the user has already provided or
approved one.

An approved plan exists when the user explicitly approves it in the current
conversation, asks to implement an existing named plan, or provides an
authoritative approved plan artifact. Entering Plan mode alone does not
authorize implementation.

Approval authorizes implementation of the scoped plan; it does not require a
multi-agent pipeline. If repository evidence materially invalidates the plan,
stop and resolve the mismatch rather than silently redesigning it.

### Subagent delegation

Delegate only work that is bounded, suited to the agent's specialization,
sufficiently independent, and worth its coordination and token cost.

Prefer subagents for context-heavy exploration, isolated implementation,
independent test work, and fresh-context review.

Use the fewest agents necessary. Do not hard-code a fixed subagent role
pipeline; choose roles from the actual task boundaries.

Parallelize independent read-heavy work when useful. Parallelize write work only
when ownership and contracts are independent and writers are isolated. Keep
concurrency low by default and increase it only when the coordination cost
remains lower than the expected benefit.

Do not ask agents to duplicate work, allow unauthorized nested delegation, or
make the primary agent repeat exploration already completed by a subagent.
Require concise evidence-based reports rather than raw logs or copied source.

If a delegated role is unavailable, the primary agent may perform the work
under the same constraints.

## Validation and completion

Run the narrowest validation that provides meaningful confidence, expanding to
the affected boundary: targeted regressions, affected unit and integration
tests, contract or migration checks, lint, formatting, type checks, builds, and
repository-specific checks.

Prefer tests at the public or integration boundary closest to the real use case.
Use unit tests for isolated invariants and defensive branches.

Do not weaken, delete, skip, or rewrite a failing test merely to make validation
pass. Change a test only when the required behavior or contract legitimately
changed, and keep the new expectation traceable to that change.

Do not claim a command passed unless it ran successfully. Do not claim full
verification unless all required validation ran successfully.

When a required check cannot run, report the implementation state separately
from the verification state and explain the remaining uncertainty.

A task is complete when the requested behavior and acceptance criteria are
satisfied, the diff remains within scope, generated artifacts follow their
authoritative workflow, all feasible required validation passes, no known
blocking review findings remain, and unavailable checks, assumptions,
limitations, and residual risks are disclosed.
