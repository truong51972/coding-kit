"use strict";

// Behavioral checks for bundled OpenCode adapters with mocked host events.
// These are not substitutes for an installed OpenCode process/E2E verification.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const Module = require("node:module");

const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "@opencode/plugin") return { Plugin: { define: (value) => value } };
  return originalLoad.call(this, request, parent, isMain);
};

function textOf(values) {
  return values.map((item) => (typeof item === "string" ? item : item.text));
}

async function openHost(major, entry, directory) {
  const adapter = require(path.resolve(entry));
  if (major === 1) {
    const hooks = await adapter.ContextManagementPlugin({ directory });
    assert.equal(typeof hooks["experimental.chat.system.transform"], "function");
    assert.equal(typeof hooks["tool.execute.after"], "function");
    return {
      async context(sessionID = "s1") {
        const output = { system: [] };
        await hooks["experimental.chat.system.transform"]({ sessionID }, output);
        return textOf(output.system);
      },
      async edit(tool, args, sessionID = "s1") {
        await hooks["tool.execute.after"]({ sessionID, tool, args }, {});
      },
      async compact(sessionID = "s1") {
        const output = { context: [] };
        await hooks["experimental.session.compacting"]({ sessionID }, output);
        return textOf(output.context);
      },
    };
  }

  const handlers = {};
  assert.equal(typeof adapter.default.setup, "function");
  await adapter.default.setup({
    location: { directory },
    session: { hook: async (name, handler) => { handlers["session." + name] = handler; } },
    tool: { hook: async (name, handler) => { handlers["tool." + name] = handler; } },
  });
  assert.equal(typeof handlers["session.context"], "function");
  assert.equal(typeof handlers["tool.execute.after"], "function");

  return {
    async context(sessionID = "s1") {
      const event = { sessionID, agent: "main", system: [] };
      await handlers["session.context"](event);
      return textOf(event.system);
    },
    async edit(tool, input, sessionID = "s1", status = "completed") {
      await handlers["tool.execute.after"]({ sessionID, tool, input, status });
    },
    async compact(sessionID = "s1") {
      const event = { sessionID, system: [] };
      await handlers["session.compaction"](event);
      return textOf(event.system);
    },
  };
}

function patch(...headers) {
  return "*** Begin Patch\n" + headers.join("\n") + "\n*** End Patch\n";
}

async function verify(major, entry, directory) {
  const host = await openHost(major, entry, directory);
  const boot = await host.context();
  assert.equal(boot.length, 1, "initial session must receive bootstrap");
  assert.match(boot[0], /Context Management is active/);
  assert.deepEqual(await host.context(), [], "bootstrap is emitted once");

  // Pure memory edits, including memory-to-memory rename, do not re-arm.
  await host.edit("apply_patch", {
    patchText: patch("*** Update File: .agents/contexts/a.md",
                     "*** Move to: .agents/contexts/b.md"),
  });
  assert.deepEqual(await host.context(), [], "memory-only rename should be silent");

  // A rename from memory into source is a meaningful source change.
  await host.edit("apply_patch", {
    patchText: patch("*** Update File: .agents/contexts/b.md",
                     "*** Move to: src/b.md"),
  });
  let output = await host.context();
  assert.equal(output.length, 1, "pending edit must not repeat bootstrap");
  assert.match(output[0], /Context Management REFLECT/);
  assert.deepEqual(await host.context(), [], "reflect signal is consumed once");

  // Mixed file patches must not be suppressed, even with a primary memory path.
  await host.edit("apply_patch", {
    filePath: ".agents/contexts/a.md",
    patchText: patch("*** Update File: .agents/contexts/a.md",
                     "*** Update File: src/main.py"),
  });
  output = await host.context();
  assert.equal(output.length, 1);
  assert.match(output[0], /Context Management REFLECT/);

  // Host variants also accept Codex-style command patches.
  await host.edit("apply_patch", {
    command: patch("*** Update File: .agents/contexts/a.md",
                   "*** Move to: ../src/outside.md"),
  });
  output = await host.context();
  assert.equal(output.length, 1);
  assert.match(output[0], /Context Management REFLECT/);

  // Source edits leave a pending pointer during compaction, but no SYNC claim.
  await host.edit("edit", { filePath: "src/main.py" });
  const compact = await host.compact();
  assert.equal(compact.length, 2, "pending reflection should be noted during compaction");
  assert.match(compact[0], /compact summary/);
  assert.match(compact[1], /unresolved REFLECT candidate pointers/);
  output = await host.context();
  assert.equal(output.length, 2, "compaction should inject compaction + REFLECT only");
  assert.match(output[0], /continuity after compaction/);
  assert.match(output[1], /Context Management REFLECT/);
  assert.deepEqual(await host.context(), []);

  console.log("OpenCode v" + major + " adapter smoke passed");
}

async function main() {
  assert.equal(process.argv.length, 4, "expected v1 and v2 esbuild bundle paths");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "coding-kit-opencode-"));
  try {
    fs.writeFileSync(path.join(root, "AGENTS.md"),
      "<!-- context-management:start -->\n" +
      "## Context Management\n### Startup\n### Context Index\n" +
      "### Project Working Conventions\n" +
      "<!-- context-management:end -->\n", "utf8");
    await verify(1, process.argv[2], root);
    await verify(2, process.argv[3], root);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
