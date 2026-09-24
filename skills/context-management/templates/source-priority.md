# Source Priority

Document the repo-specific source-of-truth hierarchy here.

## Rules

- Source files are authoritative over context files.
- Use this file to identify which documents, configs, schemas, or modules own specific kinds of facts.
- When sources drift, inspect the owning source before updating context.

## Recommended Startup

1. Read the managed Context Index in `AGENTS.md`.
2. Check the source roles below for files relevant to the task.
3. Open the owning source before editing or relying on context.
4. Load additional context shards only when they help the task.

## Source Roles

| Source or pattern | Owns | Read when |
| --- | --- | --- |
| Add project-specific source entries here. | Add owned facts here. | Add read conditions here. |

## Priority Order

- Add project-specific source priority entries here when known.
- Prefer explicit ownership and repository-defined precedence over timestamp,
  file location, or whichever artifact changed most recently.
- If priority is genuinely unresolved, record the ambiguity as an active
  assumption or ask for clarification instead of inventing authority.

## Drift Handling

- If two sources disagree, identify which source owns the disputed fact and
  apply the declared priority order.
- Treat Git/mtime signals only as review candidates; they do not prove which
  source is correct.
- If an owning source supersedes context, update the affected shard as current
  baseline during the next context sync.
