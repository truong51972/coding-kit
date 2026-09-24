---
name: celery-worker
description: Design and review production Celery workers, task boundaries, routing, lifecycle, and tests.
---

# Celery Worker Architecture

Use this skill for Celery worker systems: task contracts, retries,
acknowledgements, queue routing, worker lifecycle, Beat, Django producers, and
realistic worker tests.

## Ownership Boundary

This skill owns task design, retry and acknowledgement policy, broker-aware
routing, worker lifecycle, Beat scheduling, Django producer integration, and
Celery testing.

Use a focused pointer instead of duplicating another skill:

- For Docker, Compose, uv, or import path issues, use `python-monorepo-architecture`.
- For DI container scope, provider lifecycle, fork-safe resource construction,
  or test overrides, use `dependency-injection`. Keep this skill focused on
  Celery-specific lifecycle constraints that affect worker behavior.
- For `.agents/contexts/` startup memory, use `context-management`.

## Reference Routing

Load only the references needed for the task:

- [configuration.md](references/configuration.md): Celery app factories,
  Pydantic settings, queues, routes, broker caveats, shutdown settings, and run
  commands.
- [tasks.md](references/tasks.md): thin task wrappers, Pydantic payloads,
  retries, acknowledgement policy, idempotency, Beat, and observability.
- [testing.md](references/testing.md): service tests, task wrapper tests,
  `celery.contrib.pytest`, `pytest-celery`, eager-mode caveats, and DI override
  cleanup.
- [django.md](references/django.md): Django project setup, `CELERY_` settings,
  `@shared_task`, transaction-safe enqueueing, ORM connection hygiene,
  `django-celery-results`, `django-celery-beat`, and Django-specific tests.

## Worker Type Decision Guide

| Worker type | Guidance |
|---|---|
| IO-bound worker | Higher concurrency may be fine; keep external client lifecycle explicit |
| CPU-bound worker | Control concurrency and isolate from latency-sensitive queues |
| GPU/OCR/ML worker | Use a separate queue, low concurrency, and explicit resource lifecycle |
| Long-running task worker | Use a dedicated queue, visibility-timeout awareness, and progress tracking |
| Scheduler/Beat | Beat only schedules; workers execute; API owns state and validation |

## Reliability Policy Matrix

| Option | Use when | Avoid when | Required safeguards |
|---|---|---|---|
| `acks_late` | Process or host loss must redeliver unfinished work | Task is not idempotent | Durable idempotency key and duplicate-safe side effects |
| `task_reject_on_worker_lost` | Worker child loss should requeue work | A crash loop would repeat the same failing message | Bounded failure handling and visibility into redelivery loops |
| Bounded retries | Failure is transient and recoverable | Validation, permission, or permanent domain failures | `max_retries` and explicit exception list |
| Backoff and jitter | Many tasks may retry against the same dependency | User-visible work needs a tight retry cadence | Retry budget and latency expectation |
| Idempotency keys | Task writes data, calls external APIs, or sends notifications | Read-only task with no durable side effect | Unique constraints, job table, outbox, or upstream key |
| Deduplication | Producer can enqueue duplicates or broker can redeliver | Duplicate execution is harmless and cheap | Durable dedupe store with expiry or business state check |
| Broker visibility timeout | Redis or SQS task runtime may exceed invisibility window | RabbitMQ classic ack flow is the concern | Timeout exceeds max runtime plus retry/shutdown margin |
| `worker_prefetch_multiplier` | Long or uneven tasks block fair queue consumption | Small homogeneous tasks need throughput | Per-queue tuning and concurrency-specific testing |

## Task Contract Template

```text
Task name:
Queue:
Payload schema:
Result schema:
Idempotency key:
Retryable exceptions:
Non-retryable exceptions:
Side effects:
Progress tracking:
Observability fields:
Producer transaction behavior:
```

## Task Design Rules

- Keep Celery tasks as thin adapters: validate input, set task options, delegate
  to services, and return serializable results.
- Keep business logic in service modules that do not import Celery.
- Pass IDs and compact primitives, not ORM objects, request objects, files, or
  large blobs.
- Store large inputs and outputs in object storage and pass keys.
- Use explicit queues and routes for production workloads. Keep routing in
  Celery config or publish-time options, not service code.
- Make late-acknowledged tasks idempotent before enabling redelivery behavior.

## Django Producer Rules

- Use `transaction.on_commit()` or `delay_on_commit()` for tasks that depend on
  committed database rows.
- Pass primary keys and compact primitives, not ORM model instances.
- Let Django or the API own job state transitions when consistency matters.
- For external or heavy workers, workers may compute while Django validates and
  persists final state.
- Keep ORM connection cleanup and result backends in Django-specific references.

## Broker-Aware Recipes

| Broker | Watch for | Practical fix |
|---|---|---|
| Redis | Visibility and ack caveats, duplicate delivery after long runtime | Set visibility timeout consciously and pair late ack with idempotency |
| RabbitMQ | Queue routing, QoS, prefetch, and priority behavior | Define queues/exchanges/routes explicitly and tune prefetch by workload |
| SQS | Visibility timeout, duplicate delivery, limited routing semantics | Keep task runtime below visibility timeout and design duplicates as normal |

## Testing Minimum

- Service unit tests without Celery.
- Task wrapper tests with the service mocked or provider-overridden.
- At least one real worker integration test for reliability-sensitive tasks.
- Eager mode is allowed only as a narrow smoke test, not proof of worker
  behavior.

## Project Shape

Prefer one importable package under `src/` or `app/`:

```text
src/my_worker/
|-- main.py              # create_celery_app(), module-level app
|-- settings.py          # Pydantic settings
|-- celery_config.py     # optional config constants/helpers
|-- bootstrap.py         # worker lifecycle and DI container access
|-- containers.py        # dependency-injector providers
|-- tasks/               # thin Celery adapters
|-- services/            # framework-free business logic
|-- schemas/             # Pydantic task payload/result contracts
`-- infrastructure/      # broker clients, repositories, external APIs
```

## Symptom To Fix

| Symptom | Likely cause | Fix |
|---|---|---|
| Task runs before Django row exists | Task enqueued inside an uncommitted transaction | Use `transaction.on_commit()` or `delay_on_commit()` |
| Duplicate side effects after worker crash | `acks_late` without idempotency | Add durable idempotency and duplicate-safe writes before late ack |
| Queue appears stuck on long tasks | Prefetch too high for uneven runtime | Lower `worker_prefetch_multiplier` or isolate queue |
| GPU/OCR worker starves normal jobs | Heavy worker shares queue/concurrency with light tasks | Move to dedicated queue and tune concurrency low |
| Eager tests pass but worker fails | Eager mode bypasses broker/worker behavior | Add worker-backed integration test for task boundary |
| Worker cannot import task app | Import path or Docker layout mismatch | Use `python-monorepo-architecture` to align app packaging and Celery target |

## Completion Checklist

- [ ] Settings are validated once with Pydantic and applied as Celery config.
- [ ] Celery app creation is centralized in `create_celery_app()`.
- [ ] Queues and routes are explicit for production workloads.
- [ ] Task payloads pass IDs and compact primitives.
- [ ] Task wrappers validate input and call services without business rules.
- [ ] Retry policy targets transient exceptions only and uses bounded backoff.
- [ ] Late acknowledgement is paired with idempotency and deduplication.
- [ ] Worker lifecycle hooks accept `**kwargs`; child-process initialization is
      fast; shutdown is best-effort.
- [ ] Fork-unsafe resources are not created in the parent process.
- [ ] Tests cover service logic, task wrapper behavior, and at least one real
      worker integration path when reliability matters.
- [ ] Django producers enqueue side-effecting tasks after transaction commit.
- [ ] Run a Celery import smoke test for the configured `-A` target.
- [ ] Run the selected unit and worker-backed integration tests.
