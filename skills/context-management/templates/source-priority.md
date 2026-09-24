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

## Drift Handling

- If two sources disagree, inspect the higher-priority owning source.
- If source files supersede context, update context as current baseline during the next context sync.
