# Coding Kit

Reusable **Agent Skills** for Python backend engineering, LLM prompt design, and durable coding-agent knowledge. Each skill is self-contained under [`skills/`](skills/) and can be installed independently with the [`skills` CLI](https://github.com/vercel-labs/skills).

The collection is not tied to Codex: choose whichever agent your `skills` CLI supports (for example, Codex, Claude Code, or OpenCode). Host-specific hooks are optional and require separate setup.

## Quick start

**Prerequisite:** Node.js 22.20+ with `npm`/`npx`. No custom Coding Kit installer, Python virtual environment, or repository clone is required just to install skills.

From a project directory, run:

```sh
npx skills add truong51972/coding-kit
```

This opens the CLI's interactive selection for skills and target agents. **Project-local installation is the default.** To make a skill available across projects, add `-g`:

```sh
npx skills add truong51972/coding-kit -g -a codex
```

Install specific skills without prompts:

```sh
npx skills add truong51972/coding-kit \
  --skill context-management \
  -g -a codex -y
```

Or install all available skills for a chosen agent:

```sh
npx skills add truong51972/coding-kit --skill '*' -a codex -g -y
```

`--all` is different: it selects **all skills and all supported agents** without prompts. Use it only when that is your intention.

## Available skills

| Skill | Use it for |
| --- | --- |
| [`celery-worker`](skills/celery-worker/SKILL.md) | Celery task boundaries, acknowledgements, retries, broker routing, Django producers, worker lifecycle, and integration tests. |
| [`context-management`](skills/context-management/SKILL.md) | Lazy-loaded repository context, verified historical experiences, semantic audit, sync, maintenance, and optional continuity/failure-guard hooks. |
| [`dependency-injection`](skills/dependency-injection/SKILL.md) | Python DI and resource lifecycle across FastAPI, Celery, CLI entry points, and test overrides. |
| [`drf-api-architecture`](skills/drf-api-architecture/SKILL.md) | Django REST Framework API boundaries, serializers, scoped object access, workflows, asynchronous job endpoints, and contracts. |
| [`python-monorepo-architecture`](skills/python-monorepo-architecture/SKILL.md) | Python app/package boundaries, `uv` dependency management, Dockerfiles, Compose, and monorepo layouts. |
| [`system-prompt-builder`](skills/system-prompt-builder/SKILL.md) | Production system/developer prompts for structured extraction, RAG, tool agents, routers, evaluators, and coding agents. |

Skills have task-specific references and, where needed, helper scripts, hook adapters, examples, or tests. The agent should load relevant references on demand rather than ingesting every file.

## Discover, manage, and update

```sh
# Inspect this repository's skills without installing them
npx skills add truong51972/coding-kit --list

# Show installed skills (or only global installs)
npx skills list
npx skills ls -g

# Check for updates, then update installed skills
npx skills check
npx skills update -g
```

Use `npx skills update` for the interactive project/global update flow, or `npx skills update -p` for project-only updates. See the [CLI reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) for all supported agents, scopes, and flags.

## Optional integrations

**Context Management** is a repo-level workflow, not an automatically populated memory database. Its activation uses a managed marker/Context Index in the target repository's `AGENTS.md`, with lazy-loaded current-state shards in `.agents/contexts/`. Follow [`init.md`](skills/context-management/references/init.md) for first-time setup. Optional host hooks re-surface routing after startup, subagent creation, or compaction; see the [hook setup guide](skills/context-management/references/hooks.md).

**Verified Experiences** are now managed by `context-management`, **not installed as a separate skill**. Historical lessons remain in the target repository's `.agents/experiences/` or optional personal `$AGENTS_HOME/experiences/` notebook. The standard-library `experience_ops.py` supports metadata-first lookup, capture, lint, and retirement:

```sh
python3 ~/.agents/skills/context-management/scripts/experience_ops.py list --query pytest
python3 ~/.agents/skills/context-management/scripts/experience_ops.py lint
```

The optional Claude Code post-tool failure guard only *advises* after repeated matching failures; it never blocks commands or automatically captures experiences. Enable it explicitly with `hook_ops.py claude install --with-failure-guard`. For applicability, source authority, and host support, see [experience guidance](skills/context-management/references/experiences.md) and [hook setup](skills/context-management/references/hooks.md).

Installing a skill with `npx skills` installs its files; **it does not necessarily register runtime hooks** in Codex, Claude Code, OpenCode, or other hosts. Hook commands and paths depend on the agent, installation scope, and platform. Resolve the actual installed skill directory before configuring hooks. Do not assume that Claude's `PostToolUse` hook contract is available in Codex or T3 Code.

The repository's root [`AGENTS.md`](AGENTS.md) is a standalone set of engineering-agent instructions. It is **not** one of the installable skills and is not automatically copied into projects by `npx skills`.

## Repository structure

```text
coding-kit/
├── AGENTS.md                   # Standalone engineering-agent guidance
├── README.md
├── LICENSE
├── .github/workflows/          # Targeted regression checks
└── skills/
    ├── celery-worker/
    ├── context-management/
    ├── dependency-injection/
    ├── drf-api-architecture/
    ├── python-monorepo-architecture/
    └── system-prompt-builder/
```

Each `skills/<name>/SKILL.md` defines the skill's entry point. There is **no repository-specific `install.sh`**; use `npx skills add` to install from this source.

## Contributing and local development

```sh
git clone https://github.com/truong51972/coding-kit.git
cd coding-kit

# Preview skills discovered from the local checkout
npx skills add . --list

# Run Context Management and Experiences regression tests (stdlib unittest)
python3 -m unittest discover -s skills/context-management/tests -v
```

For prompt authoring, see [`system-prompt-builder`](skills/system-prompt-builder/README.md) and its [linter](skills/system-prompt-builder/scripts/README.md). For skill validation, inspect each `SKILL.md` frontmatter and follow the relevant skill-specific tests. Keep the package's portable install flow in the upstream `skills` CLI rather than adding another installer here.
