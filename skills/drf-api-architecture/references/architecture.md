# Architecture Reference

## Goal

Keep DRF as a clear API boundary. Keep business workflows, read composition, and database invariants in the right layers.

## Recommended app shape

For small apps, a flat module layout is acceptable:

```text
apps/<domain>/
  models.py
  services.py
  selectors.py
  serializers.py
  views.py
  urls.py
  tests.py
````

For medium and large apps, prefer packages:

```text
apps/<domain>/
  api/
    v1/
      serializers/
        __init__.py
        inputs.py
        outputs.py
        <resource>.py
      views/
        __init__.py
        <resource>.py
      urls/
        __init__.py
        <resource>.py
  models/
    __init__.py
    <resource>.py
  services/
    __init__.py
    <use_case>.py
  selectors/
    __init__.py
    <resource>.py
  permissions/
    __init__.py
    <resource>.py
  tests/
```

Do not package everything too early. Split when a file starts mixing multiple resources, multiple use cases, or unrelated concerns.

## Layer responsibilities

### Models

Use models for:

* database fields
* relationships
* constraints
* indexes
* simple properties
* small local invariants
* state helpers that do not orchestrate workflows

Avoid putting large workflows in models.

### QuerySets

Use custom QuerySets for reusable query scopes:

* `active()`
* `visible_to(user)`
* `owned_by(user)`
* `for_tenant(tenant)`
* `with_related()`
* `with_counts()`
* `ready()`
* `archived()`

QuerySet methods should be chainable and side-effect free unless intentionally implementing a bulk update/delete.

### Managers

Use Managers as model entry points. Prefer:

```python
class ResourceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

class ResourceManager(models.Manager.from_queryset(ResourceQuerySet)):
    pass

class Resource(models.Model):
    objects = ResourceManager()
```

or:

```python
class Resource(models.Model):
    objects = ResourceQuerySet.as_manager()
```

Do not put large business workflows in Managers.

### Selectors

Use selectors for read orchestration:

* object access helpers
* list queries
* filtering visible records
* applying `select_related`
* applying `prefetch_related`
* annotation and aggregation for read APIs

Example:

```python
def document_get_visible(*, user, document_id):
    return get_object_or_404(
        Document.objects.visible_to(user),
        id=document_id,
    )
```

### Services

Use services for writes and workflows:

* create/update/archive/restore
* state transitions
* multi-model writes
* transaction boundaries
* enqueueing async jobs
* audit events
* external side effects, ideally after commit

Example:

```python
@transaction.atomic
def document_create(*, project, user, title):
    document = Document.objects.create(
        project=project,
        created_by=user,
        title=title,
    )
    return document
```

## Import direction

Preferred direction:

```text
api/views -> serializers
api/views -> selectors
api/views -> services
services -> models
selectors -> models
permissions -> selectors or querysets
```

Avoid:

```text
models -> api
serializers -> views
services -> views
selectors -> views
```

## Rule of thumb

If code answers “can this user see this object?”, put it in QuerySet, selector, or permission.

If code answers “what changes should happen?”, put it in service.

If code answers “is this request payload valid?”, put it in serializer.

If code answers “how does HTTP map to application behavior?”, put it in view.