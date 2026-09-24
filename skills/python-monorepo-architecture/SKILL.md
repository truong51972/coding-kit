---
name: python-monorepo-architecture
description: Maintain Python apps/packages/infra monorepos using uv, Docker, and Compose.
---

# Python Monorepo Architecture

Maintain clean boundaries between deployable apps, shared packages, and
infrastructure in Python monorepos that use `uv`, Docker, and Docker Compose.

## Ownership Boundary

This skill owns repo layout, app/package boundaries, uv layout, Dockerfile and
Compose alignment, build context, local package wiring, and split-repo planning.

Use a focused pointer instead of duplicating another skill:

- For task reliability, retries, routing, Beat, or Django producers, use
  `celery-worker`.
- For DI container design, provider scope, resource lifecycle, or overrides, use
  `dependency-injection`.
- For durable `.agents/contexts/` memory, use `context-management`.

## Start Here

Before changing files, detect the repo mode:

- Is there a root `pyproject.toml`?
- Is there a root `uv.lock`?
- Is `[tool.uv.workspace]` present?
- Does the app have its own `uv.lock`?
- Does Compose build from the repo root or the app directory?
- Does the Dockerfile copy `packages/` or only app-local files?
- Does the app use flat imports or package-qualified imports?

Then read only the owners for the area being edited:

- `compose.yaml` root include file, if present.
- The relevant `infra/compose/*.yaml` fragment.
- The app `pyproject.toml` and `uv.lock`.
- The app Dockerfile.
- Any `packages/*/pyproject.toml` consumed by the app.

Do not use workspace-only commands such as `uv sync --package` unless the root
workspace files actually exist.

## Reference Routing

| Task | Reference |
|---|---|
| Writing or reviewing `pyproject.toml` | [pyproject-patterns.md](references/pyproject-patterns.md) |
| Writing or reviewing a Dockerfile | [dockerfile-patterns.md](references/dockerfile-patterns.md) |
| Writing or reviewing a Compose service | [compose-patterns.md](references/compose-patterns.md) |
| Adding a shared package or splitting a repo | [package-management.md](references/package-management.md) |

## Recommended Shape for New or Restructured Repositories

Preserve a coherent existing repository layout unless the task explicitly calls
for restructuring. Do not migrate a repository merely to match this skill.

When establishing a new monorepo, or when the existing repository has no stable
layout convention, this shape is a reasonable default:

```text
apps/<app>/          # Deployable applications
packages/<package>/  # Reusable Python packages with src layout
infra/compose/       # Compose fragments grouped by runtime concern
compose.yaml         # Root include file
```

Treat the shape as a recommendation rather than an invariant. Independently
managed deployable apps usually benefit from their own `pyproject.toml` and
lockfile. Use a shared root workspace only when the repository intentionally
wants shared dependency resolution. Shared packages should be explicit package
dependencies rather than ad-hoc `PYTHONPATH` or `sys.path` coupling.

## Packaging Decision Matrix

| Situation | Prefer | Why |
|---|---|---|
| App may be split into its own repo later | Independent app with app-local `pyproject.toml` and `uv.lock` | Lowest coupling |
| App is deployed independently and has heavy dependencies | Independent app with its own lockfile | Avoid installing heavy deps everywhere |
| Multiple apps must share exact dependency versions | Root uv workspace | Single lockfile consistency |
| Code is reused by multiple apps | Shared package under `packages/` | Explicit dependency boundary |
| App should be importable as a package | Packaged app with `src/<module>` | Stable imports and runtime entrypoints |
| Simple flat Django/FastAPI app | `tool.uv.package = false` when not installed as a package | Avoid fake packaging |

## Golden Examples

App-local shared package wiring:

```toml
[project]
dependencies = [
  "example-package",
]

[tool.uv.sources]
example-package = { path = "../../packages/example-package", editable = true }
```

Compose build context from `infra/compose/*.yaml`:

```yaml
services:
  example-app:
    build:
      context: ../..
      dockerfile: apps/example-app/Dockerfile
    working_dir: /app
```

Docker copy order for app-local `uv sync`:

```dockerfile
COPY apps/example-app/pyproject.toml apps/example-app/uv.lock ./
COPY packages /packages
RUN uv sync --locked --no-dev --no-install-project
COPY apps/example-app/src ./src
```

## Consistency Rules

| Concern | Must match |
|---|---|
| Dockerfile `WORKDIR` | Compose service `working_dir` |
| Dockerfile `COPY` sources | Compose `build.context` includes every copied path |
| Flat app with `tool.uv.package = false` | Flat imports and a direct runtime entrypoint |
| Packaged app with `[build-system]` | `src/<module>` imports and package-qualified runtime entrypoint |
| `--no-install-project` used | App source copied to a runtime-importable path |

Local packages must be real `[project].dependencies` entries resolved through
`[tool.uv.sources]`. Do not rely on ad-hoc `PYTHONPATH` or `sys.path` edits.

With `build.context: ../..` or another repo-root context, app-local
`.dockerignore` files are ignored by Docker. Put ignore rules at the actual
context root or use a Dockerfile-specific ignore file.

## Framework And Worker Notes

- Framework apps can be flat or packaged, but runtime config, CLI/module
  entrypoints, Docker `WORKDIR`, and Compose `working_dir` must all match.
- Worker apps with OCR, PyTorch, GPU, or other heavy dependencies should usually
  be independent deployable apps unless the repo intentionally uses a root
  workspace.
- Shared domain code should live in `packages/`, not be imported via
  `PYTHONPATH`.
- Do not force every app to install OCR, PyTorch, or worker-only dependencies
  just because one deployable app needs them.

## Symptom To Fix

| Symptom | Likely cause | Fix |
|---|---|---|
| `COPY packages/... not found` | Compose `build.context` is the app directory | Use repo-root context or stop copying repo-level packages |
| `ModuleNotFoundError` for shared package | Dependency missing from `[project].dependencies` or `[tool.uv.sources]` | Add a real dependency and re-lock |
| `uv sync --package` fails | No root uv workspace | Use app-local `uv sync` or create a real workspace |
| Runtime cannot import app | Entrypoint does not match flat/package style | Align the entrypoint with import layout |
| Code works locally but not in Docker | App-local `.dockerignore` is ignored because context is repo root | Move ignore rules to context root or Dockerfile-specific ignore |
| Dev volume shadows installed package | Compose volume mounts over installed files | Mount only source paths or intentionally run editable install |

## Workflows

### Add A Shared Package

1. Create `packages/<name>/pyproject.toml` with a real build backend and
   `src/<import_name>` target.
2. Add the distribution name to the consuming app's `[project].dependencies`.
3. Add a `[tool.uv.sources]` entry pointing at the package path.
4. Re-run `uv lock` and `uv sync --locked` from the app directory.
5. Update the Dockerfile to copy the package directory before `uv sync`.

See [package-management.md](references/package-management.md) for copyable
examples.

### Add Or Review An App

1. Choose packaging style before writing files.
2. Write `pyproject.toml` to match that style.
3. Write the Dockerfile so dependencies install before app source is copied.
4. Add a Compose service in the relevant `infra/compose/*.yaml`.
5. Verify from the correct app or workspace directory.

See [pyproject-patterns.md](references/pyproject-patterns.md),
[dockerfile-patterns.md](references/dockerfile-patterns.md), and
[compose-patterns.md](references/compose-patterns.md).

## Completion Checklist

- [ ] Repo mode was detected before choosing commands.
- [ ] Root workspace files exist before using `workspace = true` or
      `uv sync --package`.
- [ ] App has `uv.lock` if Dockerfile copies it.
- [ ] `[project].dependencies` includes local package names and
      `[tool.uv.sources]` resolves them.
- [ ] Compose context includes every path that Dockerfile `COPY`s.
- [ ] Ignore file applies at the actual build context root.
- [ ] `pyproject.toml`, `uv.lock`, and local packages are copied before app
      source for cacheable installs.
- [ ] Compose `working_dir` matches Dockerfile `WORKDIR`.
- [ ] Flat vs package import style is consistent throughout.
- [ ] Runtime entrypoint, config imports, and module paths agree.
- [ ] Dev volume mounts do not shadow installed package files.
- [ ] Run `uv lock --check` or the closest equivalent for the selected
      app/workspace.
- [ ] Run `uv sync --locked` from the correct directory.
- [ ] Run an import smoke test for local packages.
- [ ] Run `docker compose config`.
- [ ] Build only the affected service image.
- [ ] If a task queue is involved, run an import smoke test for its app target.
