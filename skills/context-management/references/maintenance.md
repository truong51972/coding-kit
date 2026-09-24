# Maintenance Lifecycle Operation

Run maintenance only when context quality needs broader structural cleanup.

## Trigger

Use maintenance when:

- A shard grows beyond roughly 4,000 tokens or 250 non-empty lines.
- There are many duplicate or near-duplicate facts.
- Shards are orphaned.
- Managed Context Index routing is wrong.
- Context contains substantial changelog or session noise.
- Repository architecture changed broadly.
- The user explicitly asks for cleanup or reset.

## Allowed

- Compact, merge, split, or rewrite shards inside `.agents/contexts/`.
- Retire a stale shard only after its durable facts are either intentionally
  removed or migrated to a clearly owned replacement.
- Update the managed Context Index in the same change whenever a shard is
  renamed, merged, split, or retired; do not leave dangling or duplicate routes.
- Keep the marker-managed block as the compact entry point and Context Index.
- Run lint, validate, and static audit after mutations.

## Not Allowed Without Explicit Request

- Delete the entire context system.
- Reinitialize an existing context system.
- Delete many shards without replacement routing.
- Move shard ownership outside `.agents/contexts/` or managed routing outside
  the `AGENTS.md` marker block.

## Retirement and Reset

Shard retirement is not a reset. Prefer a small, auditable migration: verify
ownership, move any still-durable facts, update routing, then delete the obsolete
shard. If authority is ambiguous, stop rather than discarding information.

Reset is not routine maintenance. Ask for explicit confirmation before deleting
or replacing the existing context system.
