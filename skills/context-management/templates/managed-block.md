<!-- context-management:start -->
## Context Management

### Startup

Read this managed block before non-trivial repository work. Use the Context
Index to lazy-load only the shard relevant to the task, then inspect the
owning source before acting. Source is authoritative when it conflicts with
context.

### Context Index

- [Source priority](.agents/contexts/source-priority.md): source ownership and
  conflict handling.
- [Project baseline](.agents/contexts/project-baseline.md): durable project and
  architecture baseline.
- [Active assumptions](.agents/contexts/active-assumptions.md): current open
  assumptions and constraints.

### Project Working Conventions

- Keep secrets and credentials out of logs, snapshots, task payloads, and
  durable plaintext. Treat incoming identity headers as untrusted until a
  validated gateway replaces them.
- Keep package naming, lockfile placement, prompt assets, Compose entrypoints,
  and boundary validation in repository-specific managed conventions.
<!-- context-management:end -->
