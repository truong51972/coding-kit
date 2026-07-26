---
name: plan-large-change
description: Create an evidence-based implementation plan for a substantial, cross-boundary, or high-risk engineering change. Use in Plan mode or when the user explicitly asks for a plan. Read-only; do not implement or spawn write-capable agents.
---

# Plan a large engineering change

Use this skill only to produce a plan. It does not authorize implementation.

## Entry conditions

Use this workflow when one or more of the following apply:

- ownership or execution paths are unclear;
- multiple modules, packages, applications, or services are affected;
- public APIs, external contracts, persisted state, schemas, or migrations are
  involved;
- security, authorization, concurrency, retries, cancellation, distributed
  behavior, model-visible context, or agent orchestration is involved;
- the change is a large refactor, behavioral migration, or has significant
  operational or performance risk;
- the user explicitly requests Plan mode or an implementation plan.

Do not use this workflow for localized, well-understood changes that the primary
agent can safely plan and execute directly.

## Workflow

1. Restate the concrete problem, real use case, required outcome, constraints,
   and known acceptance criteria.
2. Inspect repository instructions and the working tree. Preserve existing user
   changes and identify repository-specific commands and boundaries.
3. Spawn `code_mapper` once with the concrete feature, bug, refactor, or
   migration scope.
4. Use the mapper's evidence rather than repeating its exploration. Perform
   only targeted follow-up inspection needed to resolve material gaps.
5. Treat the requested solution as a hypothesis. Compare it with existing
   behavior, repository patterns, standard-library capabilities, framework or
   platform features, and installed dependencies.
6. Identify authoritative sources and generated artifacts. Specify the exact
   generator, CLI, migration command, compiler, formatter, or repository script
   that must produce derived files. Never plan manual edits to framework-managed
   artifacts.
7. Choose the simplest sufficient solution. Reject speculative capabilities,
   premature abstractions, unrelated cleanup, and compatibility layers not
   required by the use case.
8. Produce the plan. Do not spawn `implementer`, `test_writer`, or any other
   write-capable agent while planning.

## Required plan contents

The plan must define:

- problem, real use case, and current evidence;
- desired behavior and acceptance criteria;
- scope and explicit non-goals;
- affected entry points, execution paths, contracts, and ownership boundaries;
- implementation steps in dependency order;
- existing code and framework capabilities to reuse;
- authoritative sources and generated artifacts, including canonical commands;
- test matrix and validation strategy;
- migration, rollout, rollback, compatibility, and observability concerns when
  applicable;
- risks, assumptions, unresolved decisions, and user decisions required before
  implementation.

Each implementation step should be concrete enough to hand to `implementer`
without requiring it to redesign the architecture.

## Completion boundary

End after presenting the plan. Entering Plan mode or completing this skill does
not authorize code changes.

Implementation may begin only after the user explicitly approves the plan,
requests implementation of a named plan, provides an authoritative approved plan
artifact, or explicitly invokes `execute-approved-plan`.
