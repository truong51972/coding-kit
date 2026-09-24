# Init Operation

Use this operation when the user asks to create a fresh context system for a
repo, or repository instructions explicitly enable context management and
the managed context block is absent or the user asks to establish it.

## Goal

Create a minimal marker-managed `AGENTS.md` startup block and
`.agents/contexts/` starter shards. Do not infer a full project baseline unless
the user provides it in the request or asks you to inspect source files.

## Steps

1. Locate the repo root from the current working directory unless the user provides a path.
2. If `AGENTS.md` exists without markers, insert the generic managed block
   immediately after its H1 while preserving every other byte. If it is absent,
   create a minimal file with that block. A valid existing managed block is
   idempotent and is never overwritten, including with `--overwrite`.
3. Fail before writing when a present marker is missing its counterpart,
   markers are mismatched or duplicated, or when legacy
   `.agents/contexts/index.md` or `working-conventions.md` remains to be
   semantically migrated.
4. Run the helper script:

   ```bash
   python3 /path/to/context-management/scripts/context_ops.py init <repo-path>
   ```

5. If the user provided project details, place them in the correct shard as current-state baseline.
6. If `.agents/context.md` exists, mention that legacy context was found, but do not migrate it unless explicitly requested.
7. Keep generated files minimal and generic.

## Starter File Intent

- `source-priority.md`: list recommended startup, source roles, source priority, and conflict rules once known.
- `project-baseline.md`: store durable purpose, audience, domain, system/content shape, scope, and success criteria once known.
- `active-assumptions.md`: store assumptions, constraints, defaults, and operating limits that future sessions must preserve.
- `AGENTS.md` managed block: generic startup, shard routing, and eager
  repo-wide conventions.

## Placement Guide

- Put source ownership, document roles, config/schema authority, and read conditions in `source-priority.md`.
- Put project identity, architecture/content shape, scope boundaries, and durable narrative in `project-baseline.md`.
- Put live constraints, accepted defaults, and future-affecting assumptions in `active-assumptions.md`.
- Put only durable, repo-wide, eager-worthy conventions and shard routing in
  the managed `AGENTS.md` block.

## Adaptation Examples

- For a code repo, source roles may include package manifests, framework configs, entrypoints, schemas, migrations, tests, API specs, and deployment files.
- For a document repo, source roles may include final artifacts, drafts, reference docs, prompt helpers, checklists, and generated outputs.
- For a mixed repo, keep context organized by ownership and read conditions rather than file type alone.

## Avoid

- Do not auto-migrate legacy `.agents/context.md` or silently replace a legacy
  context layout.
- Do not invent project-specific shards before the repo needs them.
- Do not fill context files with placeholder prose that future sessions must clean up.
- `--overwrite` applies only to starter shards; it never overwrites a developed
  managed block.
