# Sync Lifecycle Operation

Use `sync` to mutate `.agents/contexts/` when a source-backed durable
repository fact changes or an authorized operating convention is adopted.
REFLECT may identify the delta, but a hook firing alone never authorizes SYNC.
Read-only requests produce a proposal instead of a write.

## Durable Deltas

Keep a candidate only when it is durable across future tasks, expensive to
rediscover, or an important invariant. Point exact API, task, schema,
configuration, migration, and implementation detail to its owning source.

Sync changes to:

- Architecture boundaries.
- Component ownership.
- Source-of-truth locations.
- Stable repository workflows.
- Stable conventions.
- Reusable quality guardrails.
- Durable invariants.
- Current project scope.
- Active assumptions.
- Recommended repository read paths.

Do not sync for a small implementation bug fix, internal rename with no contract
impact, temporary workaround, completed task history, a one-time test result, or
details already clear from source.

## Owner-first replace-before-append

Current-state context is a **projection**, not a changelog. Before editing:

1. Identify the fact's canonical owner, stable identity and applicable scope.
   If it is an execution result, dataset identity, cleanup hold or in-flight
   operation, defer to the project-owned resource; context may link to its policy.
2. Load only the owning shard and directly relevant source. Establish source
   authority **before** resolving contradictions; newest arrival is not
   automatically the newest applicable state.
3. Distinguish observation from interpretation. Where consequential, record
   evidence pointer, observed time, branch/revision/environment, verification
   procedure and who may adopt a policy. Last edited time is not verification.
4. **Update/replace** the existing canonical statement or summary first. Create
   a new entry only for a genuinely new fact or independently owned subject.
   Do not append an execution history beneath the current projection.
5. Preserve indispensable evidence and unresolved qualifications before
   compacting obsolete narrative. Never assume Git retains ignored artifacts.
6. Update the managed Context Index **only** when routing changes. Registered
   folders cover nested Markdown shards; do not add an index line per child.
   Keep `AGENTS.md` registration-only and do not alter text outside its markers.
7. Run `context_ops.py lint`, `context_ops.py validate`, and advisory
   `context_ops.py audit`. Distinguish new/relevant findings from accepted
   existing warnings. Static checks do not establish semantic correctness.

A verified fact may replace an obsolete assumption, but preserve a concise
resolution and pointer in its canonical assumption owner when needed. A
repeated, unverified assumption must not be silently promoted. See
[assumptions.md](assumptions.md).

Cleanup is part of sync. Do not run a separate cleanup flow unless maintenance
conditions apply. Project-delegated operational resources retain their own
writers, validation and retention; SYNC never becomes their state updater.

## Independent experience capture

Do not add incident history to context shards, or treat an experience as a
context delta. After resolving a non-obvious repeatable failure, consider an
explicit `experience_ops.py capture --verified` with evidence, failed approach,
root cause, scope, and a tested resolution. Skip one-off errors and unverified
hypotheses. See [experiences.md](experiences.md). Experience edits have their
own `experience_ops.py lint` gate; a successful context sync does not prove a
lesson is correct.
