---
name: execute-approved-plan
description: Execute a substantial engineering change that already has an explicitly approved plan. Orchestrates implementer, test_writer, validation, and final_reviewer sequentially. Do not use without an approved plan.
---

# Execute an approved engineering plan

This is the only default workflow that authorizes the full multi-agent delivery
sequence. Do not invoke it merely because subagents are available.

## Entry gate

Proceed only when an approved plan exists through one of these conditions:

- the user explicitly approved the plan in the current conversation;
- the user asks to implement an existing named plan;
- the user provides an authoritative plan artifact and identifies it as approved;
- the user explicitly invokes this skill against a specific plan.

Entering or leaving Plan mode alone is insufficient.

If no approved plan exists, stop at investigation or planning. Do not construct
an ad hoc swarm workflow.

## Preflight

1. Read the approved plan, acceptance criteria, scope, non-goals, validation
   strategy, and migration or rollback requirements.
2. Inspect repository instructions and the working tree. Identify and preserve
   all pre-existing user changes.
3. Confirm that the plan still matches the repository. Do not repeat broad code
   mapping when the plan already contains current evidence.
4. Re-run `code_mapper` only when the repository materially changed, the plan is
   stale, or a critical ownership or execution-path gap blocks safe execution.
5. Identify every generated or framework-managed artifact and its canonical
   generator command. Manual edits to generated artifacts are prohibited.
6. Split the plan into bounded implementation and test handoffs. Keep write
   ownership non-overlapping and sequential.

## Implementation

1. Spawn `implementer` with:
   - the approved plan and relevant evidence;
   - acceptance criteria;
   - allowed production files and boundaries;
   - explicit non-goals and prohibited changes;
   - generated artifacts and canonical generator commands;
   - required implementation validation.
2. Inspect the implementer's report, complete diff, working tree, and generated
   outputs.
3. Route architecture conflicts or plan invalidation to the primary agent. Do
   not permit the implementer to silently redesign the solution.
4. Do not continue while production implementation has an unresolved blocker.

## Tests

When behavior changes or regression coverage is required:

1. Build a behavior-focused test matrix from the approved acceptance criteria
   and actual implementation.
2. Spawn `test_writer` after production behavior and contracts are stable.
3. Provide changed production files, existing test conventions, allowed test
   files, generated snapshot commands, and required validation.
4. Inspect the test diff and results. Route production-code testability blockers
   back to `implementer`; do not let `test_writer` modify production code.

Skip `test_writer` only when the change is genuinely non-behavioral or existing
coverage already proves the acceptance criteria. Record the reason.

## Validation

Run the narrowest checks that provide meaningful confidence, then expand to the
affected boundary:

- targeted regression tests;
- affected unit and integration tests;
- contract, schema, or migration checks;
- lint and formatting checks;
- type checks;
- build and repository-specific checks.

Use authoritative generators for migrations, clients, schemas, lock files,
snapshots, manifests, and other derived artifacts. Inspect generated diffs and
validate them; do not treat successful generation as sufficient evidence by
itself.

Do not claim a command passed unless it ran successfully. Preserve command and
failure evidence in distilled form.

## Final review

After required validation is complete, spawn `final_reviewer` with:

- the approved plan and acceptance criteria;
- complete diff and relevant surrounding code;
- generated artifacts and commands used to produce them;
- validation commands and results;
- known limitations, assumptions, and unresolved risks.

The reviewer is read-only. Route blockers as follows:

- production-code or generated-artifact blockers to `implementer`;
- test-coverage blockers to `test_writer`;
- architecture or plan blockers to the primary agent;
- requirement blockers to the primary agent for user alignment.

After rework, rerun affected validation. Rerun final review when the changes
could invalidate prior review conclusions.

## Concurrency and cost controls

- Use the fewest subagents necessary.
- Run write-capable agents sequentially when files, contracts, or mutable state
  overlap.
- Parallelize only independent read-heavy work, with no more than two concurrent
  subagents unless explicitly justified.
- Do not ask agents to duplicate work already completed by another agent.
- Do not allow subagents to spawn more agents.
- If a custom agent is unavailable, the primary agent may perform that role
  directly under the same constraints and must disclose the fallback.

## Completion report

Complete only when:

- the approved use case and acceptance criteria are satisfied;
- the implementation remains within scope and follows the approved architecture;
- generated artifacts were produced through authoritative tools;
- required validation passed;
- no blocking review findings remain.

Report:

- delivered behavior and changed files;
- generators and migration commands run;
- tests and validation results;
- review outcome and rework performed;
- assumptions, limitations, unrun checks, and residual risks.
