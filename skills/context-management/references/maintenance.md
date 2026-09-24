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
- Remove stale shards only when replacement routing is clear.
- Keep the marker-managed block as the compact entry point and Context Index.
- Run lint, validate, and static audit after mutations.

## Not Allowed Without Explicit Request

- Delete the entire context system.
- Reinitialize an existing context system.
- Delete many shards without replacement routing.
- Move shard ownership outside `.agents/contexts/` or managed routing outside
  the `AGENTS.md` marker block.

## Reset

Reset is not routine maintenance. Ask for explicit confirmation before deleting
or replacing the existing context system.
