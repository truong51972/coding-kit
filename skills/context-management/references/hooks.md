# Hook-Assisted Context Delivery

Hooks are an optional runtime adapter for Context Management. They reduce the
chance that an agent forgets startup context, loses routing after compaction, or
starts a subagent without the repository context contract.

Hooks do **not** replace the lifecycle in `SKILL.md`:

- hooks answer **when to re-surface context routing**;
- `understand` decides **what context is needed**;
- semantic audit decides whether context and source still agree;
- `sync` and maintenance decide whether durable context must change.

A hook must never claim that audit or sync happened, and it must never mutate
`.agents/contexts/` automatically.

## Delivery contract

Keep hook output deliberately small:

1. Detect that `AGENTS.md` contains one valid `context-management` marker pair.
2. Inject a short routing/continuity reminder, not a context shard.
3. Tell the agent to re-read the managed block and lazy-load only the shard needed
   next.
4. Re-establish source authority after compaction or subagent creation.
5. Stay silent when Context Management is not initialized.

Do not inject all of `.agents/contexts/`, do not mirror the managed Context Index,
and do not run a hook on every model request when the host provides a narrower
lifecycle event.

## Supported host adapters

| Host | Adapter | Behavior |
| --- | --- | --- |
| Claude Code | `hooks/claude-codex-hooks.json`; opt-in `hooks/claude-failure-guard-hooks.json` | `SessionStart`/`SubagentStart` continuity; optional Bash post-tool failure detection. |
| Codex | `hooks/claude-codex-hooks.json` | Same command-hook contract; `SessionStart(source=compact)` restores routing immediately after compaction. |
| Antigravity / `agy` | `hooks/antigravity-hooks.json` | Uses `PreInvocation`, but injects only when `invocationNum == 0`. There is no native compaction event, so compact recovery is not guaranteed. |
| OpenCode V1 | `hooks/opencode/v1.ts` | Injects once per session, enriches the compact checkpoint, then performs one continuity injection after compaction. |
| OpenCode V2 | `hooks/opencode/v2.ts` | Injects once per session+agent, enriches the compact checkpoint, then performs one continuity injection after compaction. |

The adapters intentionally do not add a default `PreToolUse(Edit/Write)` path
router. That can be added later if repository experience shows it is necessary;
leaving it out keeps V1 deterministic and avoids context noise during exploration.

## Claude Code and Codex

Both hosts accept the same command-hook shape for the events used here. Merge
`hooks/claude-codex-hooks.json` into the appropriate host configuration rather
than replacing existing hooks.

Typical locations:

- Claude Code: `~/.claude/settings.json` or `<repo>/.claude/settings.json`.
- Codex project: `<repo>/.codex/hooks.json`.
- Codex global: `${CODEX_HOME:-$HOME/.codex}/hooks.json`.

Project-local Codex hooks are the default for Context Management because the
provider is useful only in repositories that opted into the managed marker. Codex
loads project-local hooks only for trusted projects.

### Registering the hook after `npx skills`

Portable skill installers install the skill files but do not necessarily register
host runtime hooks. Run the helper from the actual installed skill directory.
With no arguments it opens a small menu:

```bash
python3 ~/.agents/skills/context-management/scripts/hook_ops.py
```

The menu asks for the action and scope. Defaults are:

```text
Action: Install
Scope:  Project
```

Project scope resolves the Git root when available, falls back to the current
working directory, and writes `<project>/.codex/hooks.json`.

For scripting, use the explicit CLI. Project remains the default scope:

```bash
python3 ~/.agents/skills/context-management/scripts/hook_ops.py codex install
python3 ~/.agents/skills/context-management/scripts/hook_ops.py codex status
python3 ~/.agents/skills/context-management/scripts/hook_ops.py codex remove
```

Use global scope explicitly when the hook should apply to every Codex project:

```bash
python3 ~/.agents/skills/context-management/scripts/hook_ops.py \
  codex install --scope global
```

For non-Git projects or automation, override the project root explicitly:

```bash
python3 ~/.agents/skills/context-management/scripts/hook_ops.py \
  codex install --project-root /path/to/project
```

`CODEX_HOME` and `--codex-home` apply only to global scope. The helper discovers
`context_provider.py` relative to itself, so it does not hard-code whether the
skill was installed under `~/.agents/skills/`, `~/.codex/skills/`, or another
location.

The operation is idempotent. It removes stale Context Management registrations,
adds the current `SessionStart` and `SubagentStart` entries, and preserves
unrelated hook events, handlers, and top-level JSON fields. Invalid existing JSON
fails without rewriting the file.

`status` returns success only when both required Context Management event hooks
are present. `remove` deletes only command handlers that point to the Context
Management provider with `--host claude-codex`; unrelated hooks remain intact.

Hook registration does not bypass Codex hook trust or managed-policy controls.
Review/trust the installed hook when Codex asks. The helper also does not modify
`config.toml` or enable feature flags on the user's behalf.

The shipped manual hook template assumes the normal coding-kit canonical install
location:

```text
${AGENTS_HOME:-$HOME/.agents}/skills/context-management/
```

If the skill lives elsewhere, prefer `hook_ops.py`; it resolves the provider path
from the installed skill automatically.

The shared Python provider handles only `SessionStart` and `SubagentStart`:

- startup/resume: inject the small routing reminder;
- compact: inject a compact-continuity reminder;
- subagent: remind the child that parent-loaded shards are not assumed inherited.

No context shard content is copied into the hook response.

## Experiences: shared provider, optional Claude post-tool observer

Experience lookup is intentionally **not** injected into SessionStart, and is
not listed in the Context Index. UNDERSTAND queries `experience_ops.py list`
only when the current task involves repeated failures or historical lessons.

The same `context_provider.py` can process a Claude Code Bash
`PostToolUse`/`PostToolUseFailure` event using `failure_guard.py`. To
enable this extra runtime guard, opt in explicitly:

```bash
python3 ~/.agents/skills/context-management/scripts/hook_ops.py \
  claude install --with-failure-guard
```

This installs the usual session/subagent hooks **plus** a Claude-only post-tool
observer; no second SessionStart handler and no experience files injected.
Without the flag, installation remains the former two-event setup. The helper
removes stale handlers that point to the **old** standalone
`skills/experiences/hooks/experience_provider.py` when reinstalling; it keeps
unrelated hooks untouched. Review host-specific support before adding this
hook to Codex/T3; it is **not enabled** for them by default. Reinstalling
without the flag removes the extra managed post-tool hooks.

The optional guard only emits a non-blocking suggestion after repeated errors;
it does not capture, edit or delete lessons. State is local to the session and
written outside the repository. Unknown exit statuses are ignored if the event
does not imply failure. For hosts without a compatible post-tool lifecycle,
use `failure_guard.py observe` manually or omit the runtime guard.

After updating from the former separate `experiences` skill, remove that old
skill installation via your skill manager when convenient. Its existing
`.agents/experiences/` and personal notebook data require **no migration**.

## Antigravity / `agy`

Merge `hooks/antigravity-hooks.json` into `.agents/hooks.json` or the global
Antigravity hooks configuration.

Antigravity currently exposes `PreInvocation` rather than a dedicated
`SessionStart`/compaction lifecycle event. The adapter therefore executes at each
invocation boundary but emits context only for `invocationNum == 0`; later calls
return an empty object. This keeps token overhead near zero after bootstrap, but
there is still a small process-spawn cost for the configured command hook.

Do not emulate compaction detection by scraping the transcript. The transcript is
host-owned runtime data and would make this integration brittle. Until the host
exposes a compact lifecycle event, rely on the agent's compacted state plus normal
`understand` behavior.

## OpenCode

OpenCode exposes the compact boundary directly, which is the most important hook
for this integration. Two thin adapters are shipped because V1 and V2 use
different plugin APIs:

- V1: `experimental.chat.system.transform` plus
  `experimental.session.compacting`;
- V2: `ctx.session.hook("context")` plus `ctx.session.hook("compaction")`.

Choose the adapter that matches the installed OpenCode major version and copy or
symlink it into the repository plugin directory. For V1:

```bash
mkdir -p .opencode/plugins
cp ~/.agents/skills/context-management/hooks/opencode/v1.ts \
  .opencode/plugins/context-management.ts
```

For V2:

```bash
mkdir -p .opencode/plugins
cp ~/.agents/skills/context-management/hooks/opencode/v2.ts \
  .opencode/plugins/context-management.ts
```

OpenCode automatically loads local plugins from `.opencode/plugins/`. The
adapters keep small in-memory sets so bootstrap is injected once per session
(V1) or session+agent (V2), while a compaction marks the session for exactly one
continuity refresh.

On compaction the adapter asks the checkpoint to preserve only the active
objective, decisions, blockers/next move, and names or purpose of context shards
that materially affect the task. It explicitly avoids copying whole shards into
the summary. The first model request after compaction receives one small
continuity reminder, then normal zero-injection operation resumes.

V1 and V2 plugin implementations are not interchangeable. Re-check the upstream
plugin contract when upgrading across those major APIs.

## Overhead budget

Treat hook injection as a sparse cache invalidation mechanism, not a prompt layer.
A normal session should see approximately:

```text
startup             one small reminder
subagent start       one small reminder per child/agent
compaction           one small compact instruction + one continuity reminder
ordinary tool calls  no context injection; optional Claude Bash guard can emit
                     a single advisory when repeated failures are detected
```

The provider should remain much smaller than the shard it points to. If a future
adapter starts repeatedly injecting full context, remove or redesign that adapter.

## Failure and security rules

- No valid managed marker pair: no-op.
- Malformed hook input: fail open with no context mutation.
- Hook failure must not rewrite repository context.
- Keep command hooks read-only with respect to the repository.
- Review hook files before trusting them; they execute with the host process's
  local permissions.
- Host-specific adapters are runtime compatibility code. Durable repository facts
  remain in `AGENTS.md` and `.agents/contexts/`, not in hook scripts.

## Upstream references

- Claude Code hooks: <https://code.claude.com/docs/en/hooks>
- Codex hooks: <https://developers.openai.com/codex/hooks>
- Antigravity hooks: <https://antigravity.google/docs/hooks>
- OpenCode V1 plugins/hooks: <https://opencode.ai/docs/plugins/>
- OpenCode V2 plugins/hooks: <https://opencode.ai/v2/docs/build/plugins>
