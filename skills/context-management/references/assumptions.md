# Decision-Relevant Assumptions

An assumption is an **explicit unresolved premise**, not a source-backed fact,
an accepted rule, or every intermediate inference. Capture material assumptions
proactively; never automatically promote them because several agents reused
the same premise.

## Eligibility

Track a premise only when **all** of the following hold:

1. It materially influenced a choice, interpretation or conclusion.
2. Authoritative evidence has not established it for the relevant scope.
3. It is likely to matter across a step boundary or handoff.
4. Losing it would risk a wrong continuation or repeated investigation.

Skip disposable hypotheses, search guesses, same-step verified/rejected
premises, repeated paraphrases and operational statuses owned by a register.
When the task is read-only, disclose important assumptions in the answer or
propose tracking rather than silently modifying the repository.

## Progressive storage

- **Working**: keep a short assumption in the active task or handoff artifact.
  This is the default. Do not create a project-wide ledger for one task.
- **Tracked**: when multiple tasks/agents need one assumption or independent
  revalidation is required, use one project-designated Markdown ledger outside
  `.agents/contexts/`. The project chooses its path and single writer. An
  indexed context shard may link to it for lazy discovery.
- **Durable**: after source verification, SYNC the verified fact to its owning
  context shard. An accepted long-term *operating assumption* can enter
  `active-assumptions.md` **labeled as an assumption**, with authority, scope
  and review condition. Acceptance is a policy disposition, not proof of truth.

One canonical owner per assumption at a time. Others reference the canonical
record rather than maintaining parallel copies.

## Lightweight Markdown format (optional)

A checkbox is a review affordance, not the source of truth for state:

```markdown
- [ ] ASM-017 — provisional — Workers run as one instance
  Scope: evaluation worker / environment X / revision R
  Decision affected: retry and concurrency design
  Basis: inferred from deployment config (observed on YYYY-MM-DD)
  Verify by: check actual deployment scaling and worker identity
  Owner: orchestration coordinator
```

For resolved records, keep a short outcome, authoritative evidence pointer,
and link to any promoted context fact. A project may split a large ledger by
domain only when it materially improves targeted loading; do not auto-index
every assumption in `AGENTS.md`.

## Lifecycle

- **provisional**: unresolved; must not be reused as a verified fact.
- **verified**: supported for the documented claim, scope, time/revision and
  check; eligible for SYNC when durable.
- **rejected**: contradicted for the recorded scope, with evidence.
- **retired**: superseded, no longer relevant, or replaced; not necessarily false.

An **accepted operating assumption** is an authority-granted disposition and
remains explicitly uncertain where the evidence is insufficient.

Use meaning + scope + owning authority/dependency for deduplication. A
candidate seen again should update or reference the same record. Do not count
sibling agents or re-read occurrences as independent corroboration; there is
no default encounter threshold or promotion counter.

## Validate, promote and retire

- On consequential reuse, inspect the referenced evidence and check whether
  source/config changes affect applicability.
- Contradictory evidence suspends reliance; preserve both evidence pointers
  until authority and scope resolve the disagreement.
- Promote through SYNC with appropriate evidence **or** explicit policy
  adoption; resolve the old record and point to the new owner.
- Retire stale assumptions from active lookup without erasing unresolved
  operational obligations. Those stay with the project-owned register.
- Do not claim exhaustive automatic contradiction detection: review is scoped
  to touched sources and decisions.

No dedicated assumption database, vector index, automatic schema migration,
or always-on scanner is required for the initial version.
