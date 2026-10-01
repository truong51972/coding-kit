# Migrate Lifecycle Operation

Use **MIGRATE** when an existing repository already has Context Management but
its managed layout or storage conventions are older than the currently installed
`context-management` skill.

Migration is agent-driven because old context may contain durable knowledge that
cannot be moved or deleted safely with a mechanical rewrite.

## Trigger

Run migration when any of these is true:

- The user asks to update or migrate Context Management to the latest installed layout.
- The managed `AGENTS.md` block still stores durable repository knowledge or a large startup policy instead of acting as a small registration/index surface.
- Legacy `.agents/contexts/index.md`, `working-conventions.md`, or `.agents/context.md` exists.
- The current layout conflicts with the ownership/loading rules in the installed `SKILL.md` and templates.

When an older layout is detected during substantial repository work, migrate it
before relying on that layout if the migration is bounded and unambiguous. If
preserving existing knowledge requires a semantic decision that cannot be
verified from source, keep the ambiguity visible rather than deleting or guessing.

Do not use `init --overwrite` as a migration mechanism.

## Target

Treat the currently installed Context Management skill and templates as the
target layout. Preserve repository-specific shard names and Context Index routes;
the generic template is a shape/default, not permission to replace custom routes.

The current target keeps:

- durable knowledge under `.agents/contexts/`;
- `AGENTS.md` limited to the marker-managed activation/Context Index block;
- context shards lazy-loaded;
- hooks as optional context providers/continuity injectors only;
- semantic audit, sync, and maintenance owned by the skill lifecycle.

## Migration workflow

1. **Inventory** the existing marker-managed `AGENTS.md` block, all
   `.agents/contexts/` shards, and supported legacy context files.
2. **Preserve routing** by recording every valid existing Context Index entry and
   custom shard before changing the managed block.
3. **Semantic audit** old managed-block knowledge and legacy context against the
   owning source. Classify each useful fact as durable context, source-owned
   detail, stale history, or unresolved ambiguity.
4. **Move durable knowledge** into the smallest appropriate shard. Prefer an
   existing shard; create or split one only when targeted lazy loading becomes
   materially better.
5. **Discard only verified noise** such as stale history, duplicated source-owned
   detail, or facts disproved by authoritative source. Never discard unresolved
   information merely to match the new template.
6. **Reduce `AGENTS.md`** to the current registration-only shape while preserving
   all still-valid custom Context Index routes. Do not copy project conventions
   or architecture prose back into the managed block.
7. **Repair legacy layout** only after its durable content has been accounted for.
   Remove legacy files only when their useful content is represented in the
   current shards or verified unnecessary.
8. **Re-audit routing** so every current shard that should be discoverable is
   linked exactly once and no Context Index entry points outside the context
   directory.
9. Run `context_ops.py lint`, `context_ops.py validate`, and
   `context_ops.py audit`. Resolve deterministic findings where possible.
10. Report what moved, what was removed as verified noise, and any unresolved
    migration ambiguity. Do not claim semantic verification for areas that were
    not checked against owning source.

## Hooks

Migration does not require a hook to be installed, and hooks must not perform the
migration themselves. If the current host already has the supported hook adapter,
the migrated registration block is enough for it to resume hook-assisted
continuity.

Install or modify host/global hook configuration only when the user requests it
or repository setup explicitly owns that configuration. Do not silently mutate
unrelated user-global agent settings as part of repository migration.

## Safety

- Do not modify production source merely to make old context true.
- Do not overwrite custom shards with starter templates.
- Do not replace a custom Context Index with the generic three-entry template.
- Do not treat file recency as semantic authority.
- Do not turn migration into repository-wide architecture cleanup.
- Keep the migration diff limited to Context Management-owned files unless the
  user explicitly requests broader changes.
