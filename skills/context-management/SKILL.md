---
name: context-management
description: Manage durable repo context when AGENTS.md has the context-management managed marker or users request review, sync, cleanup, or hook-assisted continuity.
---

# Context Management

Manage current repository knowledge under `.agents/contexts/`, verified historical
lessons in the `.agents/experiences/` catalog (or optional personal notebook),
and decision-relevant unresolved assumptions under the smallest appropriate
task/project owner. Load only what the task needs.

## Activation and ownership

Apply this skill implicitly for non-trivial repository work when `AGENTS.md`
contains one valid `context-management` managed marker pair.

Own `.agents/contexts/**`, verified experience **catalog entries** and only the
small marker-managed registration block in `AGENTS.md`. Keep that block limited
to activation and the **Context Index** (individual context shards or folders).
Experience lessons are discovered by the separate catalog, never duplicated in
that index. Project-delegated resources (registers, datasets, operational holds,
run artifacts) retain their own ownership and policy, even when stored under a
historically named `.agents/experiences/` subdirectory. Never analyze or modify
the rest of `AGENTS.md`.

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

## Proactive reflection (REFLECT)

Run **REFLECT** proactively at meaningful decision/evidence boundaries and
before completion of substantive repository work; users need not request a
context update. Read [reflect.md](references/reflect.md) only when performing
the procedure. Examine only new relevant candidates, classify ownership,
verify evidence and choose **NO_CHANGE**, scoped **SYNC**, verified experience
**CAPTURE**, or **TRACK_ASSUMPTION**. Do not write for review-only/read-only
requests. Capture only consequential, unresolved assumptions; use the task
artifact by default and an optional project ledger only for cross-task reuse.
Read [assumptions.md](references/assumptions.md) when candidates qualify.
Repeated assumptions never become facts solely by frequency. Never turn
execution tracking, retries or checkpointing into this skill's responsibility.

## Optional host hooks

Host lifecycle hooks may re-surface Context Management routing at session start,
subagent start, and compaction boundaries. They are context providers/injectors,
not a second lifecycle engine: a hook firing does not mean `understand`, semantic
audit, REFLECT, `sync`, or maintenance has run, and existing hooks must not
mutate durable context. Optional future REFLECT adapters require separately
verified host lifecycle contracts, bounded execution and read-only/no-change
guards; neither `Stop` nor pre-compaction implies persistence happened.

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
4. Run **REFLECT** proactively at meaningful decision, evidence or completion
   boundaries to evaluate **new** knowledge and assumptions. NO_CHANGE is
   normal; never trigger an extra turn solely to report it. See
   [reflect.md](references/reflect.md).
5. Run **SYNC** only when durable *current repository* knowledge changed, using
   owner-first upsert rather than append-only history. Read
   [sync.md](references/sync.md). Separately capture a verified lesson only
   when it passes [experiences.md](references/experiences.md).
6. Run **MAINTENANCE** only for broad cleanup, routing problems, duplicate or
   oversized shards, large architecture changes, or explicit reset requests.
   Read [maintenance.md](references/maintenance.md).

## Storage test

Store a fact only when it is at least one of these:

- Durable across future tasks.
- Expensive to rediscover reliably.
- An important invariant, boundary, convention, or active assumption.

Do not store session summaries, task history, temporary TODOs, one-time test
results, or narration of recent edits. Track decision-relevant provisional
assumptions **outside** durable context until verified or explicitly adopted;
never treat frequency as proof. For exact API, task, schema, migration,
configuration, and implementation details, store a concise pointer to the
owning source instead of copying the detail.

## Loading rules

- Read the managed registration block in `AGENTS.md` first and use its Context
  Index as the only routing source. Index entries may point to a single Markdown
  shard or a directory ending in `/`. For a matching directory, discover child
  paths by name and open only the relevant shard, never the whole directory.
- The Context Index selects context shards; a relevant shard may link to a
  project-delegated register, policy, or assumption ledger. Follow that explicit
  link only when needed; do not treat it as a context shard or an experience.
- Stop loading context when the task scope, material constraints and owning
  sources to verify are identified. Each additional shard must answer a
  concrete task question.
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
- A folder entry covers nested Markdown shards without separate registration;
  direct file entries remain supported, including inside registered folders.
  Do not register `.agents/contexts/` itself as a catch-all.

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

- Keep every shard directly linked or covered by an indexed folder, and
  lazy-loaded independently.
- At meaningful completion, evaluate REFLECT once; preserve read-only intent.
  NO_CHANGE requires no additional tool call or persistent entry.
- Resolve conflicts in favor of source and sync only durable deltas, replacing
  stale current-state projections rather than appending task history.
- Run context `lint`/`validate` after context edits and review `audit` findings.
- Run experience `lint` after lesson edits; never treat syntax checks as proof
  that evidence or the lesson's applicability is semantically correct.
- Report accepted warnings without claiming semantic verification.
