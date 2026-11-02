# Optional Experience Hooks

The experience notebook works without hooks. The following is a thin,
opt-in Claude Code integration; merge the provided template into existing
settings instead of replacing other hooks.

Template: "skills/experiences/hooks/claude-hooks.json".
Manual configuration location: "~/.claude/settings.json" (global) or
"<repo>/.claude/settings.json" (project). Set the command path to the **actual**
installed experiences skill directory if not under AGENTS_HOME/skills.

- SessionStart: inject at most eight "name: description" entries, with a pointer
  to the catalog CLI for retrieval. Remains silent if the notebook is empty.
- PostToolUse / PostToolUseFailure for Bash: parse known command exit status,
  compute a normalized error fingerprint, and emit an advisory at three matching
  errors without observed progress.
- No durable experience edits, no raw logs in the state file, and no blocking.
- Each agent/session needs a distinct session_id; sharing a session_id causes
  its failure observations to be combined. Session state expires after 24 hours.
- Host events may not report all exit codes; unknown status is ignored instead
  of guessing from words in the output. Thus some failure loops may be missed.
- The heuristic can still report false positives on useful repeated failures.
  The suggestion is never mandatory.

Codex and T3 Code do not necessarily implement Claude's PostToolUse schema.
The existing Context Management Codex hooks cover SessionStart/SubagentStart
only: do NOT assume this template enables automatic failure detection in Codex.
Use the "failure_guard.py observe" CLI until you have verified the host's
actual post-tool event payload. No silent monkey-patching of tools or API proxy.

The SessionStart index costs tokens proportional to the number/length of
descriptions. If minimal context usage is critical, remove the SessionStart
handler and let the agent call "experience_ops.py list --query ..." on demand.

For isolated tool/hook testing:

```sh
python3 -m unittest discover -s skills/experiences/tests -v
```
