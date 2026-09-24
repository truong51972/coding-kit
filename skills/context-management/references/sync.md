# Sync Lifecycle Operation

Use `sync` to mutate `.agents/contexts/` after a task only when durable
repository knowledge changed.

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

## Steps

1. Identify the durable delta.
2. Load affected shards only.
3. Verify existing affected facts against the owning source. When source
   artifacts conflict, resolve declared ownership/priority first; do not sync
   whichever file merely changed last.
4. Remove stale, duplicated, historical, overly detailed, or misplaced content.
5. Add or rewrite durable current-state knowledge.
6. Preserve concise source references rather than copied detail.
7. Update the managed Context Index only when shard routing changes. Promote a
   fact into Project Working Conventions only when it is durable, repo-wide,
   and worth eager loading; never auto-copy content merely because headings
   match.
8. Run `context_ops.py lint`.
9. Run `context_ops.py validate`.
10. Run `context_ops.py audit`.
11. Resolve deterministic findings where possible.

Cleanup is part of sync. Do not run a separate cleanup flow unless maintenance
conditions apply.
