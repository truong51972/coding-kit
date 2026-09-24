# Engineering agent instructions

## Purpose and precedence

This file defines universal engineering principles and execution policy.
Repository-specific architecture, commands, boundaries, and validation belong
in the repository's `AGENTS.md` or a more specific nested instruction file.

The closest applicable instruction takes precedence. Repository code,
configuration, tests, CI, framework conventions, and documentation remain the
source of truth.

## Engineering principles

### Build only for real needs

Do not implement a feature merely because it is technically possible.

A production change must have:

- a concrete user, operational, or business use case;
- an observable problem or required outcome;
- explicit scope and acceptance criteria;
- evidence of the current behavior and why it is absent, incorrect, or
  insufficient.

Treat the requested solution as a hypothesis. Investigate the problem and the
existing execution path before committing to an implementation.

Clarify ambiguity that could materially affect contracts, persisted data,
security, architecture, or user-visible behavior. For low-risk ambiguity, state
the assumption, choose the simplest reversible option, and proceed.

### Prefer the simplest sufficient solution

Before writing new code, use this order:

1. Remove the need or use existing behavior or configuration.
2. Reuse an established repository implementation or pattern.
3. Use the standard library.
4. Use native framework or platform capabilities.
5. Use an already-installed dependency.
6. Add a well-established dependency only when justified.
7. Write the minimum custom code required.

Stop at the first option that satisfies the actual requirement without creating
greater net complexity.

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

### Protect generated artifacts

Do not manually create or edit artifacts generated or managed by a framework,
code generator, schema compiler, package manager, build system, or repository
script.

Identify generated artifacts through framework conventions, generated headers,
documentation, configuration, and existing commands. Modify the authoritative
source, run the canonical generator, CLI, migration command, formatter,
compiler, or script, then inspect and validate its output.

Examples include framework migrations, generated clients, lock files, compiled
schemas, generated manifests, tool-owned snapshots, and derived build outputs.

For Django schema changes, modify the authoritative models and use the
repository's migration command. Never manually create or edit files under
`migrations/`.

If an authoritative tool cannot safely produce the required artifact, report a
blocker. Do not hand-edit generated output unless the user explicitly authorizes
an exception and repository conventions permit it.

### Keep changes coherent and scoped

Prefer one self-contained behavioral change per diff. Keep required production
code and directly related tests together, but separate unrelated refactoring,
formatting, dependency upgrades, file movement, and cleanup.

Do not introduce abstractions, compatibility layers, versioning, configuration,
or infrastructure for hypothetical future requirements.

Leave affected code no harder to understand, test, operate, or change than
before, without expanding the task into general cleanup or theoretical
perfection.

## Workspace safety

Before editing, inspect the working tree and identify pre-existing changes.
Do not discard, overwrite, revert, reformat, or include unrelated user changes.
Do not run destructive Git, filesystem, database, or migration commands without
explicit authorization.

Only one write-capable agent may modify overlapping files at a time. Use
separate worktrees or isolated branches when concurrent writers are necessary.

## Execution model

### Single-agent by default

The primary agent handles localized work directly: inspection, implementation,
tests, validation, and review. Do not spawn subagents merely because they are
available.

### Workflow selection

Use a trivial workflow for typo-only, comment-only, mechanical formatting,
narrow documentation, and obvious non-behavioral configuration changes.

Use a standard workflow for localized, well-understood changes with clear
ownership and acceptance criteria. The primary agent handles these directly and
may use at most one bounded subagent when isolated exploration, test work, or a
fresh-context review materially improves confidence.

Use a planning-first workflow for substantial, cross-boundary, or high-risk
changes. Investigate the current execution path and produce a concrete
implementation plan before editing unless the user has already provided or
approved one.

An approved plan exists when the user explicitly approves it in the current
conversation, asks to implement an existing named plan, or provides an
authoritative approved plan artifact. Entering Plan mode alone does not
authorize implementation.

Approval authorizes implementation of the scoped plan; it does not require a
multi-agent pipeline. The primary agent may execute directly. Delegate only
when bounded specialization, independent work, or fresh-context review
materially improves confidence. If repository evidence materially invalidates
the plan, stop and resolve the mismatch rather than silently redesigning it.

### Subagent delegation

Delegate only work that is bounded, suited to the agent's specialization,
sufficiently independent, and worth its coordination and token cost.

Prefer subagents for context-heavy exploration, isolated implementation from an
approved plan, independent test work, and fresh-context final review.

Use the fewest agents necessary. Do not hard-code a fixed subagent role pipeline;
choose roles from the actual task boundaries. Parallelize only independent
read-heavy work.
Run agents sequentially when they share files, contracts, decisions, or mutable
state. Unless explicitly justified, do not run more than two subagents
concurrently.

Do not ask agents to duplicate work, allow unauthorized nested delegation, or
make the primary agent repeat exploration already completed by a subagent.
Require concise evidence-based reports rather than raw logs or copied source.

If a custom agent is unavailable, the primary agent may perform the same work
under the same constraints and must disclose the fallback.

## Validation and completion

Run the narrowest validation that provides meaningful confidence, expanding to
the affected boundary: targeted regressions, affected unit and integration
tests, contract or migration checks, lint, formatting, type checks, builds, and
repository-specific checks.

Prefer tests at the public or integration boundary closest to the real use case.
Use unit tests for isolated invariants and defensive branches.

Do not claim a command passed unless it ran successfully. Report unrun or
failing checks and the remaining uncertainty.

A task is complete only when the approved use case and acceptance criteria are
satisfied, the diff remains within scope, generated artifacts came from
authoritative tools, required validation passed, no blocking review findings
remain, and assumptions, limitations, and unrun checks are disclosed.
