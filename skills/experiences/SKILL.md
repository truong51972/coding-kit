---
name: experiences
description: Reuse verified past failures as a small personal or project experience notebook, with optional advisory failure-loop detection.
---

# Experiences

A separate, source-grounded notebook of reusable **verified lessons**. Context
Management describes the current repository; a skill describes a procedure;
an experience captures a failed approach, root cause, and validated resolution.

## Storage and trust

- Project notebook: "<repo>/.agents/experiences/*.md" (reviewable in Git).
- Personal notebook: "<AGENTS_HOME>/experiences/*.md", with AGENTS_HOME
  defaulting to "~/.agents" (available across repositories).
- Same slug: the project lesson shadows the global lesson, including if retired.
- An experience is an **advisory** historical record, never an instruction or
  authoritative source. Confirm applicability against current code/config/tests.
- Do not write credentials, secrets, user data, copied transcripts, or raw logs.
- Never turn a transient failure into a durable experience automatically.

## Discover: metadata first, details on demand

Use a cheap, deterministic index instead of reading every experience:

```sh
python3 /path/to/experiences/scripts/experience_ops.py list --limit 12
python3 /path/to/experiences/scripts/experience_ops.py list --query "pytest import"
python3 /path/to/experiences/scripts/experience_ops.py show pytest-wrong-interpreter
```

"list" prints only name, description, path (or --json for structured output).
It searches personal + local notebooks and applies lightweight keyword ranking.
The optional SessionStart hook injects at most eight index entries, not files.
Never load all experiences merely because a session started or resumed.

## Capture: only after verifying a resolution

Before capturing, establish symptoms, the failed approach, root cause,
validated resolution, applicability boundary, and evidence (test/PR/source
reference). Prefer one small reusable lesson over a chronological incident log.
For exact code, configuration, or commands that change, store pointers to source.

```sh
python3 /path/to/experiences/scripts/experience_ops.py capture \
  --name pytest-wrong-interpreter \
  --description "Import errors when pytest uses the wrong interpreter" \
  --symptoms "ModuleNotFoundError in pytest only" \
  --failed-approach "Repeatedly reinstalling packages" \
  --root-cause "The test runner was outside the project environment" \
  --resolution "Use the configured project interpreter and rerun tests" \
  --applicability "Only when interpreter mismatch is confirmed" \
  --evidence "Validated by passing pytest using the project interpreter" \
  --tags "python,pytest,environment" --verified
```

Default capture scope is project; pass "--scope global" only for truly
cross-project lessons. The command refuses to overwrite an existing filename
and needs explicit --verified. It does not independently prove the evidence.

Run lint after edits. To stop recommending an invalid lesson, use retire
(which preserves the record):

```sh
python3 /path/to/experiences/scripts/experience_ops.py lint
python3 /path/to/experiences/scripts/experience_ops.py retire pytest-wrong-interpreter
```

Frontmatter intentionally supports only single-line name, description, status,
tags; no YAML dependency. Each lesson has the six required "##" sections.
Keep descriptions <=240 characters and each file <=16 KiB. Resolve duplicates
by merging manually; never let parallel agents race to overwrite a lesson.

## Optional runtime failure guard

The detector and durable notebook are independent. Failure guard operates on
command exit codes and normalized error fingerprints; it emits a one-time
**suggestion** after three repeated failures without observed test-count
improvement. A successful command or improved failed-test count resets the
streak. It never blocks tools, invokes an LLM, edits repository context, or
auto-saves lessons.

For a host-independent tool wrapper, provide a stable session id and command
output via stdin:

```sh
printf '%s\n' 'ModuleNotFoundError: sample' | \
python3 /path/to/experiences/scripts/failure_guard.py observe \
  --session-id my-session --command 'uv run pytest' --exit-code 1
```

Each execution of the command above is an observation; after a third matching
failure it prints a hint. Real hooks can supply automatic observations.
Runtime state contains hashes/counters only and is written to
"~/.local/state/coding-kit/experience-guard/" or XDG_STATE_HOME.

## Hook setup and portability

See [references/hooks.md](references/hooks.md). Opt-in Claude Code templates
cover SessionStart, PostToolUse, PostToolUseFailure on Bash; host capabilities
must be verified before reusing events on Codex/T3 or other harnesses. When
there is no compatible PostToolUse hook, use the manual observer or just the
catalog; never claim automatic loop detection is active.

## Scope boundary

Keep the existing context-management marker, Context Index, source authority,
semantic audit, sync and maintenance behavior unchanged. These new experience
hooks are optional, advisory, and do not write ".agents/contexts/**".
