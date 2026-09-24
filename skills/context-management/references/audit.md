# Semantic Audit Lifecycle Operation

Semantic audit is an agent reasoning workflow. It is not the same as
`context_ops.py audit`, which reports only deterministic static quality signals.
The helper's Git/mtime signal identifies drift candidates; it does not establish
that context is semantically stale or current.

## Trigger

Run a scoped semantic audit when:

- A context fact directly affects an implementation or review decision.
- Context and source appear to conflict.
- The task changes a source root that context references.
- The user asks for architecture, consistency, or correctness review.
- You are preparing to change a context fact and are not sure it is still true.
- Context says a dependency, component, workflow, or invariant exists but source
  does not appear to support it.
- A durable assumption may have been resolved or invalidated.

## Scope

Audit only the relevant slice:

```text
affected shards
+
the marker-managed `AGENTS.md` block
+
owning source files
+
directly relevant tests, config, and canonical docs
```

Do not audit the whole repository by default.
Treat the managed block as the Context Index; do not inspect or modify content
outside its markers.

## Checks

Look for:

- Context-source contradictions.
- Context that copies source-of-truth details instead of referencing source.
- Managed startup routing that eagerly bundles several shards for a task category.
- Local Markdown links that do not resolve from their containing context file.
- Generic sandbox, network, or untracked-file agent rules that are not repo facts.
- Cross-shard overlap.
- Facts stored in the wrong shard.
- Stale assumptions.
- Missing durable constraints that future tasks need.
- Context too specific or too broad to be useful.
- Source references that no longer exist.

## Output

Keep the audit result in working memory for the task and feed durable deltas into
`sync`. Do not store long audit history in context.
