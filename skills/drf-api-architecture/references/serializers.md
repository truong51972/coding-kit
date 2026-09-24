# Serializers Reference

## Serializer responsibilities

Serializers should:

- validate request input
- normalize primitive values
- serialize response output
- provide clear API contracts

Serializers should not:

- contain large business workflows
- call queues or background workers
- call external services
- perform multi-model transactions
- hide authorization decisions
- decide ownership or tenant scope

## Prefer explicit input and output serializers

For non-trivial APIs, separate request and response serializers.

Example:

```python
class ResourceCreateInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)

class ResourceOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "title", "description", "created_at", "updated_at"]
````

This avoids accidental exposure of write-only/internal fields.

## When to use ModelSerializer

Use `ModelSerializer` when the API shape closely follows the model.

Good for:

* detail output
* list output
* simple CRUD
* admin/internal APIs with known field exposure

Be careful with:

```python
fields = "__all__"
```

Avoid it for public or semi-public APIs unless the project explicitly accepts exposing every model field.

## When to use Serializer

Use `Serializer` for:

* command endpoints
* non-model inputs
* filter query params
* async job triggers
* workflow actions
* input that does not map 1:1 to a model

Example:

```python
class ResourcePublishInputSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)
    force = serializers.BooleanField(default=False)
```

## Server-owned fields

Do not allow clients to set server-owned fields such as:

* `user`
* `owner`
* `created_by`
* `updated_by`
* `tenant`
* `organization`
* `project`
* `status`
* `current_version`
* `created_at`
* `updated_at`
* permission flags
* internal metadata

Set those fields in services using trusted context.

## Validation placement

Use serializer validation for request-local validation:

```python
def validate_title(self, value):
    if not value.strip():
        raise serializers.ValidationError("Title cannot be blank.")
    return value
```

Use services for validation involving:

* current user permissions
* cross-object state
* transactions
* race-prone checks
* state transitions
* external systems
* multi-model invariants

Use database constraints for invariants that must never be violated.

## Nested serializers

Nested serializers are fine for read output.

For nested writes, be cautious. Prefer explicit services when nested writes:

* create multiple models
* update multiple aggregates
* require ownership checks
* require transactions
* have complex validation
* trigger side effects

## SerializerMethodField

Use `SerializerMethodField` sparingly.

It is acceptable for simple derived values.

Avoid using it for:

* expensive queries per object
* permission checks per object
* external service calls
* hidden business logic

If a field needs related data for a list endpoint, optimize the queryset with `select_related`, `prefetch_related`, or annotations.

## Partial update

For PATCH APIs, make partial update semantics explicit.

Do not let clients update fields that should be immutable or state-controlled.

Example:

```python
class ResourceUpdateInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
```

Then apply changes in service:

```python
def resource_update(*, resource, actor, data):
    for field, value in data.items():
        setattr(resource, field, value)
    resource.updated_by = actor
    resource.save(update_fields=[*data.keys(), "updated_by", "updated_at"])
    return resource
```

## Error messages

Prefer stable field-level validation errors.

Avoid returning many different ad-hoc error formats across endpoints.

If the API needs machine-readable frontend handling, include stable error codes through a project-wide convention.

````

