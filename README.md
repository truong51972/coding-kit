# Codex Skills

A collection of reusable Codex skills for Python services, application architecture, and durable repository context. Each skill is self-contained under [`skills/`](skills/).

## Repository layout

```text
.
├── skills/
│   ├── celery-worker/
│   ├── context-management/
│   ├── dependency-injection/
│   ├── drf-control-plane-api/
│   └── python-monorepo-architecture/
├── install.sh
├── LICENSE
└── README.md
```

The installer discovers directories matching `skills/*/SKILL.md` in the selected Git ref. New skills become installable without changes to `install.sh`.

## Available skills

| Skill | Purpose |
| --- | --- |
| `celery-worker` | Design and review Celery tasks, routing, lifecycle, scheduling, and tests. |
| `context-management` | Set up and maintain durable, source-grounded repository context. |
| `dependency-injection` | Design Python dependency injection across FastAPI, Celery, CLI, resources, and tests. |
| `drf-control-plane-api` | Build and review Django REST Framework control-plane APIs and workflows. |
| `python-monorepo-architecture` | Maintain Python monorepos built with uv, Docker, and Compose. |

## Requirements

Installation requires a POSIX-compatible `sh`, `curl`, `tar`, and `mktemp`.

Skills are installed into `${AGENTS_HOME:-$HOME/.agents}/skills`.

## Quick install

Install every skill from the latest `main` branch:

```sh
curl -fsSL https://raw.githubusercontent.com/truong51972/coding-kit/main/install.sh | sh -s -- --all
```

## Interactive selection

Run the installer without a selection to open a multi-select menu. The menu reads from `/dev/tty`, so it still works when the script itself is piped to `sh`:

```sh
curl -fsSL https://raw.githubusercontent.com/truong51972/coding-kit/main/install.sh | sh
```

If no TTY is available, pass `--all` or explicit skill names.

## Non-interactive installation

Install selected skills:

```sh
curl -fsSL https://raw.githubusercontent.com/truong51972/coding-kit/main/install.sh \
  | sh -s -- celery-worker context-management
```

List the skills discovered on `main`:

```sh
curl -fsSL https://raw.githubusercontent.com/truong51972/coding-kit/main/install.sh \
  | sh -s -- --list
```

## Custom refs

Use `--ref` with a branch or tag. The installer downloads and scans that ref rather than relying on a fixed skill list:

```sh
curl -fsSL https://raw.githubusercontent.com/truong51972/coding-kit/main/install.sh \
  | sh -s -- --ref develop --all
```

## Custom `AGENTS_HOME`

Set `AGENTS_HOME` to install somewhere other than `~/.agents`:

```sh
curl -fsSL https://raw.githubusercontent.com/truong51972/coding-kit/main/install.sh \
  | AGENTS_HOME="$HOME/custom-agents" sh -s -- --all
```

## Updates and verification

Every run downloads the current archive for the selected ref. Selected skills are staged and validated before their installed directories are replaced completely. Skills that were not selected, including skills from other sources, are preserved.

Verify an installation with:

```sh
find "${AGENTS_HOME:-$HOME/.agents}/skills" -mindepth 2 -maxdepth 2 -name SKILL.md -print
```

Restart Codex or begin a new session after installing or updating skills.

## Local development

Clone the repository, then symlink each local skill into your agent home so edits are immediately available:

```sh
git clone https://github.com/truong51972/coding-kit.git
cd skills
mkdir -p "${AGENTS_HOME:-$HOME/.agents}/skills"
for skill_file in skills/*/SKILL.md; do
  [ -f "$skill_file" ] || continue
  skill_dir=$(cd "$(dirname "$skill_file")" && pwd)
  ln -s "$skill_dir" "${AGENTS_HOME:-$HOME/.agents}/skills/$(basename "$skill_dir")"
done
```

Validate all skill directories during development with the Codex `skill-creator` validator:

```sh
for skill_file in skills/*/SKILL.md; do
  python3 /path/to/skill-creator/scripts/quick_validate.py "$(dirname "$skill_file")"
done
```
