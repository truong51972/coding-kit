import { readFile } from "node:fs/promises"
import { join } from "node:path"
import type { Plugin } from "@opencode-ai/plugin"

const MANAGED_BLOCK_START = "<!-- context-management:start -->"
const MANAGED_BLOCK_END = "<!-- context-management:end -->"

const BOOTSTRAP_CONTEXT =
  "Context Management is active in this repository. Read only the marker-managed Context Management block in AGENTS.md before non-trivial work. Use its Context Index to lazy-load only the shard needed next; verify decisions against owning source, which is authoritative. Hooks only restore routing/continuity; semantic audit, sync, and maintenance remain context-management skill behavior."

const COMPACT_CONTEXT =
  "Context Management continuity after compaction. Re-read the marker-managed block in AGENTS.md, then reload only the shard directly needed for the active task; do not bulk-load context. Treat owning source as authoritative and continue the existing task from the compacted summary. Audit, sync, and maintenance behavior remains unchanged and is not performed by this hook."

const COMPACTION_PROMPT =
  "When writing this checkpoint, preserve the current objective, decisions, blockers, next move, and the names or purpose of any .agents/contexts shards that materially affect the task. Do not copy whole context shards into the summary. Preserve source-versus-context conflicts as unresolved until verified; owning source remains authoritative."

async function hasManagedContext(root: string): Promise<boolean> {
  try {
    const text = await readFile(join(root, "AGENTS.md"), "utf8")
    const start = text.indexOf(MANAGED_BLOCK_START)
    const end = text.indexOf(MANAGED_BLOCK_END)
    return start >= 0 && end > start
  } catch {
    return false
  }
}

export const ContextManagementPlugin: Plugin = async ({ directory }) => {
  if (!(await hasManagedContext(directory))) return {}

  const bootstrapped = new Set<string>()
  const refreshAfterCompaction = new Set<string>()

  return {
    "experimental.chat.system.transform": async (input, output) => {
      const sessionID = input.sessionID
      if (!sessionID) return

      const afterCompaction = refreshAfterCompaction.delete(sessionID)
      if (bootstrapped.has(sessionID) && !afterCompaction) return

      output.system.push(afterCompaction ? COMPACT_CONTEXT : BOOTSTRAP_CONTEXT)
      bootstrapped.add(sessionID)
    },

    "experimental.session.compacting": async (input, output) => {
      refreshAfterCompaction.add(input.sessionID)
      output.context.push(COMPACTION_PROMPT)
    },
  }
}
