# API Layer Reference

## Choose the smallest suitable DRF primitive

### Use APIView when

Use `APIView` for command-style or workflow endpoints:

- approve
- reject
- archive
- restore
- submit
- publish
- commit
- import
- export
- start-processing
- retry-job

Example:

```python
class ResourceArchiveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, resource_id):
        resource = resource_get_visible(
            user=request.user,
            resource_id=resource_id,
        )

        archive_resource(
            resource=resource,
            actor=request.user,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
````

### Use GenericAPIView when

Use `GenericAPIView` when you want DRF hooks such as:

* `get_queryset`
* `get_serializer_class`
* `get_object`
* pagination
* filtering
* schema support

but the endpoint is not a simple generic CRUD view.

### Use generic views when

Use generic views for simple resource operations:

* `ListAPIView`
* `RetrieveAPIView`
* `CreateAPIView`
* `UpdateAPIView`
* `DestroyAPIView`
* `ListCreateAPIView`
* `RetrieveUpdateDestroyAPIView`

Good fit:

```python
class ResourceListAPIView(ListAPIView):
    serializer_class = ResourceListOutputSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return resource_list(user=self.request.user)
```

### Use ViewSet when

Use `ViewSet` when multiple actions belong naturally to one resource namespace.

Use carefully. A ViewSet with many custom `@action`s can become harder to reason about than separate explicit views.

### Use ModelViewSet when

Use `ModelViewSet` only when the resource is truly CRUD-like and business rules are simple.

Avoid `ModelViewSet` when:

* create/update has complex workflows
* permissions vary heavily per action
* actions are mostly commands
* each action needs different input/output serializers
* side effects or jobs are involved
* object access is complex

## Views should be thin

A view may:

* check authentication/permission
* parse and validate input
* fetch scoped object/queryset
* call service or selector
* serialize output
* choose HTTP status code

A view should not:

* contain large business workflows
* directly call storage, queues, or external APIs unless this is intentionally an integration endpoint
* build complex database queries inline
* perform unscoped object lookup
* mutate many models without a service

## Prefer request-aware get_queryset

Use `get_queryset()` for request-aware filtering:

```python
def get_queryset(self):
    return Resource.objects.visible_to(self.request.user)
```

Avoid relying on a static `queryset` for APIs that need ownership, tenant scoping, or request-specific filtering.

## Object access pattern

Always scope before lookup:

```python
resource = get_object_or_404(
    Resource.objects.visible_to(request.user),
    id=resource_id,
)
```

Avoid:

```python
resource = get_object_or_404(Resource, id=resource_id)
```

unless the object is truly public or globally accessible.

## Input/output serializer pattern

For non-trivial endpoints:

```python
input_serializer = ResourceCreateInputSerializer(data=request.data)
input_serializer.is_valid(raise_exception=True)

resource = resource_create(
    actor=request.user,
    **input_serializer.validated_data,
)

output_serializer = ResourceDetailOutputSerializer(resource)
return Response(output_serializer.data, status=status.HTTP_201_CREATED)
```

## Response status guide

Use common HTTP statuses consistently:

* `200 OK`: successful read or update with body
* `201 Created`: resource created
* `202 Accepted`: async job accepted
* `204 No Content`: successful mutation with no body
* `400 Bad Request`: validation or malformed input
* `401 Unauthorized`: missing/invalid authentication
* `403 Forbidden`: authenticated but not allowed
* `404 Not Found`: not visible or does not exist
* `409 Conflict`: state conflict or concurrency conflict
* `422 Unprocessable Entity`: optional convention for semantic validation, only if project uses it consistently

For private resources, returning `404` for non-visible objects is often safer than leaking existence with `403`.

## Pagination

List endpoints should be paginated by default unless the result set is guaranteed small.

Do not serialize large unbounded querysets.

## Filtering and searching

Keep filtering explicit.

Good:

```python
class ResourceFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Resource.Status.choices, required=False)
    search = serializers.CharField(required=False, allow_blank=True)
```

Then pass validated filters to selector:

```python
filters = filter_serializer.validated_data
queryset = resource_list(user=request.user, filters=filters)
```

Avoid parsing complex query params directly throughout the view.

## URL design

Use resource-oriented URLs for CRUD/read:

```text
/api/v1/resources/
/api/v1/resources/{resource_id}/
```

Use action URLs for commands:

```text
/api/v1/resources/{resource_id}/archive/
/api/v1/resources/{resource_id}/restore/
/api/v1/resources/{resource_id}/submit/
```

Use nested URLs when the parent scope is meaningful:

```text
/api/v1/projects/{project_id}/resources/
```

Avoid deeply nested URLs beyond 2–3 levels unless there is a strong reason.

## Versioning

Prefer clear API version namespaces for production APIs:

```text
/api/v1/...
/api/v2/...
```

Keep versioned serializers, views, and urls together.

Do not silently change request/response shapes within the same public API version.

````

---

# `references/serializers.md`

```markdown
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