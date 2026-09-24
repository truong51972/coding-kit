# Model, QuerySet, Manager & Object Access Reference

## Model role

Models should define the durable data shape:

* fields
* relationships
* indexes
* constraints
* simple properties
* small local invariants

Avoid putting large workflows directly on models.

Acceptable:

```python
@property
def is_archived(self):
    return self.archived_at is not None
```

Risky:

```python
def approve_and_send_email_and_enqueue_job_and_write_audit_log(self):
    ...
```

Move complex workflows to services.

## Custom QuerySet for reusable scopes

Use custom QuerySets for reusable, chainable query logic.

Example:

```python
class ResourceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def archived(self):
        return self.filter(deleted_at__isnull=False)

    def owned_by(self, user):
        return self.filter(owner=user)

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        return self.owned_by(user)

    def with_related(self):
        return self.select_related("owner").prefetch_related("tags")
```

Then:

```python
class Resource(models.Model):
    objects = ResourceQuerySet.as_manager()
```

Keep authorization scope and lifecycle scope separate.

Good:

```python
Resource.objects.visible_to(user).active()
```

Avoid hiding lifecycle rules inside `visible_to()` unless the project intentionally defines visibility that way.

## QuerySet vs selector

Use QuerySet methods for small reusable scopes.

Use selectors when reads become use-case specific.

QuerySet:

```python
Resource.objects.visible_to(user).active()
```

Selector:

```python
def resource_list_for_dashboard(*, user, filters):
    qs = Resource.objects.visible_to(user).active().with_related()
    qs = apply_resource_filters(qs, filters=filters)
    return qs
```

Use selectors when the query needs:

* request-specific filtering
* multiple optional filters
* annotations
* aggregation
* query optimization for a specific response shape
* permission-aware object access
* non-trivial composition of QuerySet methods

## Manager guidelines

Managers are entry points for model-level queries.

Good:

```python
class ResourceManager(models.Manager.from_queryset(ResourceQuerySet)):
    pass
```

Then:

```python
class Resource(models.Model):
    objects = ResourceManager()
```

Avoid putting multi-step workflows in Managers.

Managers should not become a hidden service layer.

## Default manager and base manager

Be careful with filtered default managers.

For soft delete, the project must intentionally decide:

```python
objects = ActiveResourceManager()
all_objects = ResourceManager()
```

Important rule:

Do not filter away rows in the base manager unless you fully understand the consequences. Related object resolution and admin/internal operations may need unfiltered access.

If using soft delete, define conventions clearly:

* Which manager is default?
* Which manager is unfiltered?
* Which manager should APIs use?
* Which manager should admin/internal jobs use?
* Should `base_manager_name` or `default_manager_name` be set explicitly?

A common convention:

```python
class Resource(models.Model):
    objects = ActiveResourceManager()
    all_objects = ResourceManager()

    class Meta:
        base_manager_name = "all_objects"
        default_manager_name = "objects"
```

Only use this pattern if the team understands the consequences.

For many projects, a safer and more explicit approach is:

```python
class Resource(models.Model):
    objects = ResourceManager()
```

Then API code chooses the scope explicitly:

```python
Resource.objects.visible_to(user).active()
```

## Object access must be scoped

Never fetch private resources with an unscoped lookup.

Bad:

```python
resource = Resource.objects.get(id=resource_id)
```

Good:

```python
resource = get_object_or_404(
    Resource.objects.visible_to(user),
    id=resource_id,
)
```

For multi-tenant APIs:

```python
resource = get_object_or_404(
    Resource.objects.for_tenant(tenant).visible_to(user),
    id=resource_id,
)
```

For active-only endpoints:

```python
resource = get_object_or_404(
    Resource.objects.visible_to(user).active(),
    id=resource_id,
)
```

For restore, audit, or history endpoints, do not use `.active()` unless the endpoint intentionally excludes archived records.

## List and detail visibility should match

If a user cannot see an object in list, they usually should not retrieve it by detail endpoint.

Use the same visibility base query:

```python
def get_queryset(self):
    return Resource.objects.visible_to(self.request.user)
```

Then add endpoint-specific lifecycle filters:

```python
def get_queryset(self):
    return Resource.objects.visible_to(self.request.user).active()
```

The key rule is consistency: list and detail endpoints should not accidentally use different ownership or tenant scopes.

## Parent-child object access

When a URL contains both parent and child IDs, validate the relationship in the scoped query.

Bad:

```python
resource = get_object_or_404(
    Resource.objects.visible_to(request.user),
    id=resource_id,
)
```

when the URL is:

```text
/api/v1/projects/{project_id}/resources/{resource_id}/
```

Better:

```python
resource = get_object_or_404(
    Resource.objects.visible_to(request.user),
    id=resource_id,
    project_id=project_id,
)
```

This prevents accessing a visible child through the wrong parent context.

## Use select_related and prefetch_related deliberately

Use `select_related` for ForeignKey and OneToOne relations that will be accessed.

Use `prefetch_related` for ManyToMany, reverse ForeignKey, and larger related sets.

Example:

```python
def resource_list(*, user):
    return (
        Resource.objects
        .visible_to(user)
        .active()
        .select_related("owner", "organization")
        .prefetch_related("tags")
    )
```

Do not scatter query optimization inside serializers. If serializer reads relations, the queryset or selector should prepare them.

## Avoid N+1 queries

Watch for N+1 when serializers access:

* foreign keys
* reverse relations
* many-to-many fields
* computed properties that query the database
* `SerializerMethodField`

Fix with:

* `select_related`
* `prefetch_related`
* `Prefetch`
* annotations
* moving computed values into selector/queryset

Example:

```python
from django.db.models import Count

def resource_list(*, user):
    return (
        Resource.objects
        .visible_to(user)
        .active()
        .select_related("owner")
        .annotate(comment_count=Count("comments"))
    )
```

Avoid doing this inside a serializer method:

```python
def get_comment_count(self, obj):
    return obj.comments.count()
```

on every item in a list response.

## Constraints

Use database constraints for invariants that must hold even under concurrency.

Examples:

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["organization", "slug"],
            name="uniq_resource_slug_per_org",
        ),
        models.CheckConstraint(
            check=Q(status__in=["draft", "active", "archived"]),
            name="valid_resource_status",
        ),
    ]
```

Do not rely only on serializer validation for critical uniqueness or state invariants.

Good candidates for constraints:

* scoped uniqueness
* valid status values
* non-negative counters
* mutually exclusive fields
* one active object per scope when supported by partial unique constraints

## Indexes

Add indexes for fields frequently used in:

* filters
* ordering
* joins
* uniqueness checks
* soft-delete filters
* tenant scoping
* status dashboards
* job polling

Example:

```python
class Meta:
    indexes = [
        models.Index(fields=["organization", "status", "-created_at"]),
    ]
```

Do not add indexes blindly. They improve reads but cost write overhead and storage.

A useful API-oriented rule:

If an endpoint frequently filters by a field, orders by a field, or combines tenant/status/time filters, review whether the model needs an index.

## Model validation

Do not assume `clean()` runs automatically on `save()`.

If a service depends on model validation, call `full_clean()` explicitly or enforce the rule with database constraints and service checks.

Example:

```python
@transaction.atomic
def resource_create(*, actor, data):
    resource = Resource(created_by=actor, **data)
    resource.full_clean()
    resource.save()
    return resource
```

Do not call `full_clean()` blindly in every save path unless the project intentionally uses that convention.

## Transactions

Use `transaction.atomic()` for multi-step writes that must succeed or fail together.

Example:

```python
@transaction.atomic
def resource_publish(*, resource, actor):
    resource.status = Resource.Status.PUBLISHED
    resource.published_by = actor
    resource.save(update_fields=["status", "published_by", "updated_at"])
    return resource
```

Use transactions for:

* multi-model writes
* state transitions
* counters and quotas
* job row creation with resource updates
* audit records that must match the write
* operations that must be all-or-nothing

## Locking

Use `select_for_update()` for race-prone state transitions.

Example:

```python
@transaction.atomic
def resource_activate(*, resource_id, actor):
    resource = (
        Resource.objects
        .select_for_update()
        .get(id=resource_id)
    )

    if resource.status != Resource.Status.READY:
        raise ResourceStateError("Resource is not ready.")

    resource.status = Resource.Status.ACTIVE
    resource.activated_by = actor
    resource.save(update_fields=["status", "activated_by", "updated_at"])
    return resource
```

Keep transactions short. Do not hold database locks while calling slow external services.

Use locking when two concurrent requests could:

* publish the same resource twice
* create duplicate active versions
* consume the same quota
* overwrite state transitions
* create duplicate jobs for the same resource/state

## Side effects and transaction commit

If a service must enqueue a job, send an email, or call an external system after a DB write, prefer triggering the side effect after the transaction commits.

Pattern:

```python
@transaction.atomic
def resource_create(*, actor, data):
    resource = Resource.objects.create(created_by=actor, **data)

    transaction.on_commit(
        lambda: enqueue_resource_created_job(resource_id=resource.id)
    )

    return resource
```

`transaction.on_commit()` prevents the side effect from running if the database transaction rolls back.

It does not roll back the already-committed transaction if the callback fails after commit. If callback failure must be recoverable, use an explicit recovery strategy such as a transactional outbox, enqueue status field, broker publish confirmation, or a periodic recovery task.

## Practical review checklist

When reviewing model/queryset/object access for a DRF API, check:

* Are private object lookups scoped before lookup?
* Are list and detail endpoints using compatible visibility rules?
* Are tenant/project/organization relationships validated?
* Are `visible_to()` and lifecycle scopes like `active()` kept clear?
* Are reusable query scopes placed in QuerySet methods?
* Are use-case-specific reads placed in selectors?
* Are large workflows kept out of models and managers?
* Are constraints used for durable invariants?
* Are frequent filters/orderings indexed?
* Are serializers protected from N+1 queries?
* Are state transitions wrapped in transactions?
* Are race-prone transitions locked when needed?
* Are external side effects delayed until after commit when appropriate?
