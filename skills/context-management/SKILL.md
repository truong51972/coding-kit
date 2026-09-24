---
name: context-management
description: Manage durable repo context when AGENTS.md has the context-management managed marker or users request setup, review, sync, or cleanup.
---

# Context Management

Manage reusable startup memory under `.agents/contexts/`. Keep it compact,
source-grounded, durable, and scoped to future work rather than the current
session.

## Activation and ownership

Apply this skill implicitly for non-trivial repository work when `AGENTS.md`
contains one valid `context-management` managed marker pair. Do not initialize
context merely because the skill is available. Use [init.md](references/init.md)
only when the user requests setup or repository instructions enable it.

Own only `.agents/contexts/**` and the marker-managed block in `AGENTS.md`.
Never analyze or modify the rest of `AGENTS.md`; initialization may locate its
H1 only to insert the managed block without changing surrounding bytes. Let
source code, schemas, configuration, tests, and canonical documentation own
their exact details. Treat source as authoritative whenever it conflicts with
context.

## Lifecycle

1. Run **UNDERSTAND** before substantial work. Read
   [understand.md](references/understand.md).
2. Work against owning source files.
3. Run a scoped **SEMANTIC AUDIT** when context affects a decision, conflicts
   with source, references changed source roots, or the user requests review.
   Read [audit.md](references/audit.md).
4. Run **SYNC** only when durable repository knowledge changed. Read
   [sync.md](references/sync.md).
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
configuration, or implementation details, store a concise pointer to the
owning source instead of copying the detail.

## Loading rules

- Read the managed block in `AGENTS.md` first and use its Context Index as the
  only routing source.
- Load one shard at a time only when the current task needs it.
- Do not map a task category to a default bundle of several shards.
- Load `source-priority.md` only for ownership, canonical read order, source
  conflicts, or drift repair.
- Keep routing and eager repository-wide conventions in the managed block.
- Add or split shards only when more targeted loading becomes useful.

## Compatibility

Interpret old `update` requests as **SYNC**. Fold routine `clear` cleanup into
**SYNC**; use **MAINTENANCE** for broad cleanup. Never reset, delete, or
reinitialize an existing context system without an explicit request.

## Helper CLI

Use the deterministic helper for structure and hygiene, not semantic proof:

```bash
python3 /path/to/context-management/scripts/context_ops.py init [repo-path]
python3 /path/to/context-management/scripts/context_ops.py lint [repo-path]
python3 /path/to/context-management/scripts/context_ops.py scan [repo-path]
python3 /path/to/context-management/scripts/context_ops.py validate [repo-path]
python3 /path/to/context-management/scripts/context_ops.py audit [repo-path]
python3 /path/to/context-management/scripts/context_ops.py audit --strict [repo-path]
python3 /path/to/context-management/scripts/context_ops.py status [repo-path]
```

Keep all existing commands compatible. Treat `scan` as the `lint` alias.
Treat `lint` as the hygiene gate and `validate` as the structure gate. Treat
`audit` as advisory: warnings return `0`, structural errors return `2`, and
`--strict` makes warnings return `1`.

Static drift findings are candidates only. Git activity, mtimes, link checks,
size, duplication, and identifier density do not establish semantic alignment.
All JSON output must retain `semantic_source_verification.status:
not_performed`.

## Completion

- Keep every shard linked from the managed Context Index and lazy-loaded
  independently.
- Resolve conflicts in favor of source and sync only durable deltas.
- Run `lint` and `validate` after context edits; review `audit` findings.
- Report accepted warnings without claiming semantic verification.
