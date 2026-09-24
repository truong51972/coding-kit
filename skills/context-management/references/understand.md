# Understand Lifecycle Operation

Run this operation automatically before non-trivial repository work when
`AGENTS.md` contains the valid context-management managed marker pair.

## Goal

Load the smallest useful amount of context needed to work accurately.
`understand` is lazy-loading: parse the marker-managed block in `AGENTS.md`,
then open one linked shard only when the current task gives a clear reason.

## Trigger

Run before:

- Implementation that touches multiple files or repository contracts.
- Debugging that depends on repository structure.
- Code review.
- Architecture or system design work.
- Refactoring.
- Test design.
- Repository documentation work.
- Planning that affects source, workflow, or durable repo behavior.

Skip for independent syntax questions, text rewriting unrelated to the repo, and
trivial tasks that do not need repository knowledge.

## Steps

1. Read the marker-managed block in `AGENTS.md` first. Use its Context Index as
   the sole shard-routing source.
2. Determine the task scope from the user request and repository paths already
   implicated by the task.
3. Decide from the index which shard, if any, is needed next.
   Load shards individually; do not preload a multi-shard bundle merely because
   the task matches a broad category.
4. Read `source-priority.md` only when the task involves source ownership,
   canonical read order, resolving conflicting documentation, or
   detecting/repairing context drift.
5. If `source-priority.md` is loaded, follow its source roles to decide which
   source files to open.
6. Read any other shard only when it directly affects the current task.
7. Open source files when they own the requested change or are needed to verify context.
8. If context and source files disagree, trust the owning source and treat the
   affected context fact as stale.
9. If source files disagree with each other, use explicit ownership and priority
   rules from `source-priority.md`. Recency alone is not authority. If no rule
   resolves the conflict, keep the ambiguity visible and ask rather than guess.
10. Keep a note for the later sync phase when a durable context fact appears
    drifted.

## Selection Heuristics

- Load `source-priority.md` for source ownership, read order, file roles, source-of-truth conflicts, or drift repair.
- Load `project-baseline.md` for product, domain, architecture, document narrative, scope, or audience questions.
- Load `active-assumptions.md` when decisions depend on constraints, defaults, limits, or unresolved operating assumptions.
- Load optional shards only when the managed Context Index says they are relevant to the task.

## Source Verification

Open owning source before relying on a context fact that directly affects an
implementation or review decision. Context can route you to source, but source
is authoritative.

## If Context Is Missing

If the managed marker block is absent or invalid, say that no context system is
initialized. Do not create it unless the user asks for `init` or clearly
requests setup.

## Avoid

- Do not load every shard by default.
- Do not make task categories eager-loading shortcuts for several shards.
- Do not read `source-priority.md` automatically after the managed block; it is also lazy-loaded.
- Do not treat context files as proof that source files are current.
- Do not edit context during `understand` unless the user explicitly asks.
