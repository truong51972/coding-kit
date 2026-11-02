---
name: context-management
description: Manage durable repo context when AGENTS.md has the context-management managed marker or users request review, sync, cleanup, or hook-assisted continuity.
---

# Context Management

Manage two distinct forms of durable memory: current repository facts under
`.agents/contexts/` and verified historical lessons under `.agents/experiences/`
(or optional personal `$AGENTS_HOME/experiences/`). Load only what the task needs.

## Activation and ownership

Apply this skill implicitly for non-trivial repository work when `AGENTS.md`
contains one valid `context-management` managed marker pair.

Own `.agents/contexts/**`, `.agents/experiences/**`, and only the small
marker-managed registration block in `AGENTS.md`. Keep that block limited to
activation and the **Context Index** (context shards only). Experience files
are discovered by the separate catalog, never duplicated in that index.
Never analyze or modify the rest of `AGENTS.md`.

Let source code, schemas, configuration, tests, and canonical documentation own
their exact details. Treat source as authoritative whenever it conflicts with
context. When two source artifacts disagree, resolve authority from explicit
ownership and priority rules before deciding what context is stale; do not let
recency alone choose the winner.

## Experience memory (on demand)

For debugging, repeated errors, previously failed approaches, or explicit
lesson-reuse requests, consult [experiences.md](references/experiences.md).
First query **only names/descriptions** using `experience_ops.py list --query`;
open one matching lesson with `show` only if applicable. Do not scan the
notebook for routine tasks or inject all lessons at session start.

Store only verified, reusable failures with an explicit applicability boundary,
failed approach, root cause, validated resolution and evidence. Context describes
what is true **now**; experiences describe what was learned **before**. Both are
advisory compared with owning source/config/tests. Do not automatically write
lessons from hooks; preserve separate review/retirement for experience records.

## Optional host hooks

Host lifecycle hooks may re-surface Context Management routing at session start,
subagent start, and compaction boundaries. They are context providers/injectors,
not a second lifecycle engine: a hook firing does not mean `understand`, semantic
audit, `sync`, or maintenance has run, and hooks must not mutate durable context.

Keep hook output small and pointer-oriented. Re-read the managed registration
block and lazy-load only the shard needed next rather than injecting full shards.
An optional Claude Code **post-tool** guard can suggest a strategy change after
repeated failures, but never edits experiences or blocks execution. It is
*not* automatically available in Codex/T3 without a verified event contract.
See [hooks.md](references/hooks.md) for host compatibility and opt-in setup.

## Lifecycle

1. Run **UNDERSTAND** before substantial work. Read
   [understand.md](references/understand.md).
2. For a relevant prior failure, consult matching experience metadata and load
   one lesson only when useful. Then work against owning source files.
3. Run a scoped **SEMANTIC AUDIT** when context affects a decision, conflicts
   with source, references changed source roots, or the user requests review.
   Read [audit.md](references/audit.md).
4. Run **SYNC** only when durable *current repository* knowledge changed. Read
   [sync.md](references/sync.md). Separately capture a verified lesson only
   when it passes the experience storage test in [experiences.md](references/experiences.md).
5. Run **MAINTENANCE** only for broad cleanup, routing problems, duplicate or
   oversized shards, large architecture changes, or explicit reset requests.
   Read [maintenance.md](references/maintenance.md).

## Storage test

Store a fact only when it is at least one of these:

- Durable across future tasks.
- Expensive to rediscover reliably.
- An important invariant, boundary, convention, or active assumption.

Do not store session summaries, task history, temporary TODOs, one-time test
results, or narration of recent edits. For exact API, task, schema, migration,
configuration, and implementation details, store a concise pointer to the
owning source instead of copying the detail.

## Loading rules

- Read the managed registration block in `AGENTS.md` first and use its Context
  Index as the only routing source.
- Treat hook-injected reminders as routing signals only; they do not count as a
  loaded shard or as source verification.
- After compaction, re-establish the managed block and only the context directly
  needed for the active task. Do not bulk-reload all shards.
- Load one shard at a time only when the current task needs it.
- Do not map a task category to a default bundle of several shards.
- Load `source-priority.md` only for ownership, canonical read order, source
  conflicts, or drift repair.
- Keep current repository facts in `.agents/contexts/` and historical lessons in
  `.agents/experiences/`; `AGENTS.md` is only an activation/context index surface.
- Add or split shards only when more targeted loading becomes useful.

## Rare operations

For explicit first-time setup, read [init.md](references/init.md). For an
explicit migration request or clearly legacy Context Management layout, read
[migrate.md](references/migrate.md). Keep both flows out of normal work.

## Compatibility

Interpret old `update` requests as **SYNC**. Fold routine `clear` cleanup into
**SYNC**; use **MAINTENANCE** for broad cleanup. Never reset, delete, or
reinitialize an existing context system without an explicit request.

## Helper CLI

Use the deterministic helper for structure and hygiene, not semantic proof:

```bash
python3 /path/to/context-management/scripts/context_ops.py lint [repo-path]
python3 /path/to/context-management/scripts/context_ops.py scan [repo-path]
python3 /path/to/context-management/scripts/context_ops.py validate [repo-path]
python3 /path/to/context-management/scripts/context_ops.py audit [repo-path]
python3 /path/to/context-management/scripts/context_ops.py audit --strict [repo-path]
python3 /path/to/context-management/scripts/context_ops.py status [repo-path]
```

Rare setup/migration commands belong in their reference workflows instead of
the hot-path skill instructions.

Keep all existing commands compatible. Treat `scan` as the `lint` alias.
Treat `lint` as the hygiene gate and `validate` as the structure gate. Treat
`audit` as advisory: warnings return `0`, structural errors return `2`, and
`--strict` makes warnings return `1`.

Static drift findings are candidates only. Git activity, mtimes, link checks,
size, duplication, and identifier density do not establish semantic alignment.
Drift checks are shard-local so a recently edited shard cannot hide an older
stale shard. All JSON output must retain
`semantic_source_verification.status: not_performed`.

## Experience CLI

```bash
python3 /path/to/context-management/scripts/experience_ops.py list --query 'pytest import'
python3 /path/to/context-management/scripts/experience_ops.py show pytest-wrong-interpreter
python3 /path/to/context-management/scripts/experience_ops.py lint
```

The separate `failure_guard.py observe` CLI remains available for hosts with no
compatible post-tool hook. See [experiences.md](references/experiences.md).

## Completion

- Keep every shard linked from the managed Context Index and lazy-loaded
  independently.
- Resolve conflicts in favor of source and sync only durable deltas.
- Run context `lint`/`validate` after context edits and review `audit` findings.
- Run experience `lint` after lesson edits; never treat syntax checks as proof
  that evidence or the lesson's applicability is semantically correct.
- Report accepted warnings without claiming semantic verification.
