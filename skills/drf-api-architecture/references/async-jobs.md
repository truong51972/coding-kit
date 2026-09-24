# Async Jobs Reference

## When to return 202 Accepted

Return `202 Accepted` when the API accepts work that will complete later.

Examples:

* document processing
* imports
* exports
* report generation
* batch updates
* indexing
* long-running external calls
* ML/AI pipeline execution
* webhook retry
* background reconciliation

## Endpoint responsibility

The DRF endpoint should:

* authenticate and authorize the caller
* validate input
* fetch scoped objects
* call a service
* create or enqueue a job through the service
* return job/resource status

The endpoint should not run the long task inline.

## Response shape

Use a stable response shape:

```json
{
  "job_id": "job_123",
  "status": "queued",
  "resource_id": "res_123"
}
```

Optionally include a polling URL:

```json
{
  "job_id": "job_123",
  "status": "queued",
  "resource_id": "res_123",
  "status_url": "/api/v1/jobs/job_123/"
}
```

## Service pattern

Use a service to create the job record and schedule enqueueing after commit.

```python
@transaction.atomic
def resource_start_processing(*, resource, actor, options):
    job = Job.objects.create(
        type=Job.Type.RESOURCE_PROCESSING,
        status=Job.Status.QUEUED,
        created_by=actor,
        resource_id=resource.id,
        payload=options,
    )

    transaction.on_commit(
        lambda: enqueue_resource_processing_job(job_id=job.id)
    )

    return job
```

This pattern prevents enqueueing a job for a database transaction that later rolls back.

It does not guarantee the broker enqueue succeeds after commit. If enqueue failure matters, add a recovery strategy.

## View pattern

```python
class ResourceProcessAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, resource_id):
        resource = resource_get_visible(
            user=request.user,
            resource_id=resource_id,
        )

        input_serializer = ResourceProcessInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        job = resource_start_processing(
            resource=resource,
            actor=request.user,
            options=input_serializer.validated_data,
        )

        output_serializer = JobAcceptedOutputSerializer(job)
        return Response(output_serializer.data, status=status.HTTP_202_ACCEPTED)
```

## Idempotency

For endpoints that may be retried, consider idempotency.

Useful cases:

* payment-like operations
* imports
* webhooks
* batch jobs
* expensive processing
* mobile clients with unstable networks

Possible approaches:

* client-provided idempotency key
* unique job per resource/state
* deduplicate by payload hash
* reject duplicate active jobs with `409 Conflict`
* return existing job if one is already queued/running

Example:

```python
@transaction.atomic
def resource_start_processing(*, resource, actor, options):
    existing_job = (
        Job.objects
        .filter(
            resource_id=resource.id,
            type=Job.Type.RESOURCE_PROCESSING,
            status__in=[Job.Status.QUEUED, Job.Status.RUNNING],
        )
        .first()
    )

    if existing_job:
        return existing_job

    job = Job.objects.create(
        type=Job.Type.RESOURCE_PROCESSING,
        status=Job.Status.QUEUED,
        created_by=actor,
        resource_id=resource.id,
        payload=options,
    )

    transaction.on_commit(
        lambda: enqueue_resource_processing_job(job_id=job.id)
    )

    return job
```

Use stronger idempotency when duplicate work is expensive or unsafe.

## State transitions

Do not allow invalid transitions.

Bad:

```python
resource.status = request.data["status"]
resource.save()
```

Good:

```python
resource_submit_for_review(resource=resource, actor=request.user)
```

Inside service:

```python
if resource.status != Resource.Status.DRAFT:
    raise ResourceStateError("Only draft resources can be submitted.")
```

For race-prone transitions, use transactions and locking.

```python
@transaction.atomic
def resource_submit_for_review(*, resource_id, actor):
    resource = (
        Resource.objects
        .select_for_update()
        .get(id=resource_id)
    )

    if resource.status != Resource.Status.DRAFT:
        raise ResourceStateError("Only draft resources can be submitted.")

    resource.status = Resource.Status.IN_REVIEW
    resource.submitted_by = actor
    resource.save(update_fields=["status", "submitted_by", "updated_at"])

    return resource
```

## Job and resource status

Separate job status from resource status when possible.

Resource status describes the business object:

* draft
* active
* archived
* processing
* failed

Job status describes the background execution:

* queued
* running
* succeeded
* failed
* cancelled

Avoid mixing them unless the domain is intentionally simple.

Good:

```text
Resource.status = processing
Job.status = running
```

Then after completion:

```text
Resource.status = active
Job.status = succeeded
```

or:

```text
Resource.status = failed
Job.status = failed
```

## Error handling

Async endpoints should define:

* what happens if job row creation fails
* what happens if enqueue fails
* whether a duplicate active job is allowed
* how the frontend/client observes failure
* retry behavior
* whether the operation is idempotent
* whether failed jobs can be retried
* whether cancellation is supported

Important rule:

`transaction.on_commit()` prevents enqueueing when the database transaction rolls back.

It does not roll back the already-committed database transaction if enqueueing fails after commit.

If enqueue failure must be recoverable, use one of:

* transactional outbox
* recovery task that scans queued-but-not-enqueued jobs
* enqueue status field, e.g. `pending`, `queued`, `enqueue_failed`
* broker publish confirmation when supported
* periodic reconciliation between job table and broker state

## Transactional outbox pattern

Use an outbox when enqueue reliability matters.

Basic idea:

1. In the same DB transaction, write the business state and an outbox message.
2. Commit the transaction.
3. A separate dispatcher reads unsent outbox messages.
4. Dispatcher publishes messages to the broker.
5. Dispatcher marks outbox messages as sent.

This avoids losing work when the database commit succeeds but broker publish fails.

Minimal shape:

```python
@transaction.atomic
def resource_start_processing(*, resource, actor, options):
    job = Job.objects.create(
        type=Job.Type.RESOURCE_PROCESSING,
        status=Job.Status.PENDING_ENQUEUE,
        created_by=actor,
        resource_id=resource.id,
        payload=options,
    )

    OutboxMessage.objects.create(
        topic="resource.processing.requested",
        payload={"job_id": str(job.id)},
    )

    return job
```

Then a dispatcher process publishes the outbox message and updates state.

## External side effects

Do not call slow external systems inside DB transactions.

Prefer:

1. write DB state
2. commit transaction
3. enqueue job or side effect
4. let worker perform slow work
5. worker updates job/resource state

Avoid:

```python
@transaction.atomic
def resource_process_inline(*, resource):
    resource.status = Resource.Status.PROCESSING
    resource.save(update_fields=["status", "updated_at"])

    call_slow_external_api(resource)

    resource.status = Resource.Status.ACTIVE
    resource.save(update_fields=["status", "updated_at"])
```

Better:

```python
@transaction.atomic
def resource_start_processing(*, resource, actor):
    resource.status = Resource.Status.PROCESSING
    resource.save(update_fields=["status", "updated_at"])

    job = Job.objects.create(
        type=Job.Type.RESOURCE_PROCESSING,
        status=Job.Status.QUEUED,
        created_by=actor,
        resource_id=resource.id,
    )

    transaction.on_commit(
        lambda: enqueue_resource_processing_job(job_id=job.id)
    )

    return job
```

## Polling endpoint

For async jobs, provide a way for clients to observe progress.

Example URL:

```text
/api/v1/jobs/{job_id}/
```

Example response:

```json
{
  "id": "job_123",
  "status": "running",
  "resource_id": "res_123",
  "progress": {
    "current": 42,
    "total": 100
  },
  "error": null
}
```

Keep the polling response stable.

## Retry endpoint

If retries are supported, make them explicit.

Example URL:

```text
/api/v1/jobs/{job_id}/retry/
```

Rules should be clear:

* who can retry
* which statuses can be retried
* whether retry creates a new job or reuses the old job
* whether retry increments attempt count
* whether retry is idempotent

## Cancellation endpoint

If cancellation is supported, make it explicit.

Example URL:

```text
/api/v1/jobs/{job_id}/cancel/
```

Rules should be clear:

* who can cancel
* which statuses can be cancelled
* whether cancellation is best-effort
* what happens if worker already finished
* how resource status is updated after cancellation

## Practical review checklist

When reviewing an async DRF endpoint, check:

* Does it return `202 Accepted` for long-running work?
* Does the view avoid running slow work inline?
* Is the object lookup scoped before enqueueing?
* Is the input serializer explicit?
* Is job creation handled in a service?
* Is duplicate job behavior defined?
* Is the operation idempotent or intentionally non-idempotent?
* Are invalid state transitions rejected?
* Are race-prone transitions protected by transactions or locks?
* Are external side effects outside DB transactions?
* Is `transaction.on_commit()` used correctly?
* Is enqueue failure recoverable if it matters?
* Is there a polling endpoint or status response?
* Are retry/cancel semantics defined when supported?
* Are API tests covering successful enqueue, invalid state, unauthorized user, and duplicate active jobs?
