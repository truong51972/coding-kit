import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { Plugin } from "@opencode/plugin"

const MANAGED_BLOCK_START = "<!-- context-management:start -->"
const MANAGED_BLOCK_END = "<!-- context-management:end -->"

const BOOTSTRAP_CONTEXT =
  "Context Management is active in this repository. Read only the marker-managed Context Management block in AGENTS.md before non-trivial work. Use its Context Index to lazy-load only the shard needed next; verify decisions against owning source, which is authoritative. Hooks only restore routing/continuity; semantic audit, sync, and maintenance remain context-management skill behavior. At substantive completion perform bounded REFLECT; NO_CHANGE requires no persistence."

const COMPACT_CONTEXT =
  "Context Management continuity after compaction. Re-read the marker-managed block in AGENTS.md, then reload only the shard directly needed for the active task; do not bulk-load context. Treat owning source as authoritative and continue the existing task from the compacted summary. Audit, sync, and maintenance behavior remains unchanged and is not performed by this hook."

const REFLECT_PROMPT =
  "Context Management REFLECT: before completing this substantive change, evaluate only new material knowledge and decision-relevant assumptions. Prefer NO_CHANGE when none; verify source and owner before SYNC/CAPTURE. No transcript/changelog storage, and no operational CHECKPOINT."

const WRITE_TOOLS = new Set(["write", "edit", "multiedit", "notebookedit", "apply_patch"])

function isKnowledgeWrite(args: unknown): boolean {
  if (!args || typeof args !== "object") return false
  const record = args as Record<string, unknown>
  const target = record.filePath ?? record.file_path ?? record.path ?? record.notebook_path
  const patch = record.patch ?? record.patchText ?? record.patch_text
  const paths = typeof target === "string" ? [target] :
    typeof patch === "string" ? Array.from(patch.matchAll(/^\*\*\* (?:Add|Update|Delete) File: (.+)$/gm), m => m[1]) : []
  if (!paths.length) return false
  return paths.every(target => {
    const path = target.replaceAll("\\", "/")
    return ["/.agents/contexts/", "/.agents/experiences/", "/.agents/assumptions/"].some(x => path.includes(x)) ||
      [".agents/contexts/", ".agents/experiences/", ".agents/assumptions/"].some(x => path.startsWith(x))
  })
}

const COMPACTION_PROMPT =
  "When writing the compact summary, preserve the current objective, decisions, blockers, next move, and the names or purpose of any .agents/contexts shards that materially affect the task. Do not copy whole context shards into the summary. Preserve source-versus-context conflicts as unresolved until verified; owning source remains authoritative."

async function hasManagedContext(root: string): Promise<boolean> {
  try {
    const text = await readFile(join(root, "AGENTS.md"), "utf8")
    const starts = text.split(MANAGED_BLOCK_START).length - 1
    const ends = text.split(MANAGED_BLOCK_END).length - 1
    if (starts !== 1 || ends !== 1) return false
    const start = text.indexOf(MANAGED_BLOCK_START) + MANAGED_BLOCK_START.length
    const end = text.indexOf(MANAGED_BLOCK_END)
    return end >= start
  } catch {
    return false
  }
}

export default Plugin.define({
  id: "context-management",
  async setup(ctx) {
    if (!(await hasManagedContext(ctx.location.directory))) return

    const bootstrapped = new Set<string>()
    const refreshAfterCompaction = new Set<string>()
    const pendingReflect = new Set<string>()

    await ctx.session.hook("context", (event) => {
      const key = `${event.sessionID}:${event.agent}`
      const afterCompaction = refreshAfterCompaction.delete(event.sessionID)
      if (bootstrapped.has(key) && !afterCompaction && !pendingReflect.has(event.sessionID)) return

      event.system.push({
        type: "text",
        text: afterCompaction ? COMPACT_CONTEXT : BOOTSTRAP_CONTEXT,
      })
      bootstrapped.add(key)
      if (pendingReflect.delete(event.sessionID)) {
        event.system.push({ type: "text", text: REFLECT_PROMPT })
      }
    })

    await ctx.tool.hook("execute.after", (event) => {
      if (event.status !== "completed" || !WRITE_TOOLS.has(event.tool.toLowerCase())) return
      if (!isKnowledgeWrite(event.input)) pendingReflect.add(event.sessionID)
    })

    await ctx.session.hook("compaction", (event) => {
      refreshAfterCompaction.add(event.sessionID)
      event.system.push({ type: "text", text: COMPACTION_PROMPT })
      if (pendingReflect.has(event.sessionID)) {
        event.system.push({ type: "text", text: "Keep unresolved REFLECT candidate pointers; no durable write is implied." })
      }
    })
  },
})
