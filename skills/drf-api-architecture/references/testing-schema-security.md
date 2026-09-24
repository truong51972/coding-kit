# Testing, Schema & Security Reference

## Test layers

Use different test layers for different risks.

### Service tests

Test business rules:

- create/update/archive/restore behavior
- state transitions
- transaction behavior
- invalid states
- side effects scheduled
- job creation

### Selector/QuerySet tests

Test read visibility and query composition:

- user can see own resources
- user cannot see others' resources
- tenant scoping works
- archived/deleted rows are included/excluded correctly
- filters return expected objects

### API tests

Test HTTP contract:

- auth required
- permission enforced
- request validation
- success status code
- response shape
- error shape
- cross-user access
- pagination
- schema when useful

## Required authorization tests

For private resources, every detail/update/delete/command endpoint should have tests like:

- unauthenticated request is rejected
- user A can access own object
- user B cannot access user A's object
- non-visible object returns expected status, often 404
- list endpoint does not leak non-visible objects

## Test example

```python
class ResourceDetailAPITests(APITestCase):
    def test_user_cannot_access_other_users_resource(self):
        user_a = UserFactory()
        user_b = UserFactory()
        resource = ResourceFactory(owner=user_a)

        self.client.force_authenticate(user=user_b)

        response = self.client.get(f"/api/v1/resources/{resource.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
````

## Query count tests

For list endpoints with related serializers, consider query count tests.

Example intent:

```python
with self.assertNumQueries(5):
    response = self.client.get("/api/v1/resources/")
```

Do not overfit exact query counts for volatile endpoints. Use where N+1 risk is important.

## Schema

For non-trivial endpoints, explicitly annotate schema.

Example with drf-spectacular:

```python
@extend_schema(
    request=ResourceCreateInputSerializer,
    responses={201: ResourceOutputSerializer},
)
class ResourceCreateAPIView(APIView):
    ...
```

For command endpoints:

```python
@extend_schema(
    request=ResourcePublishInputSerializer,
    responses={202: JobAcceptedOutputSerializer},
)
```

## Schema rules

Schema should show:

* request body
* response body
* status codes
* query parameters
* path parameters
* auth requirements when supported
* error responses when useful

Do not rely only on automatic schema generation for command-style APIs.

## Permissions

Authentication identifies the caller. Permissions decide whether access is allowed.

Use project-wide defaults that are safe.

Avoid accidentally making endpoints public.

For public endpoints, mark the decision clearly and add tests.

## Object-level authorization

Broken object-level authorization is a common API risk.

Any endpoint accepting object IDs must ensure:

* the object is scoped to the caller
* parent-child relationships are validated
* tenant/project/org ownership is checked
* list and detail visibility are consistent

Bad:

```python
resource = Resource.objects.get(id=resource_id)
```

Good:

```python
resource = get_object_or_404(
    Resource.objects.visible_to(request.user),
    id=resource_id,
)
```

## Mass assignment

Do not expose sensitive model fields for client writes.

Sensitive examples:

* owner
* tenant
* organization
* role
* status
* is_staff
* is_superuser
* created_by
* updated_by
* approved_by
* internal metadata

Use explicit input serializers.

## Throttling

Consider throttling for:

* login/session endpoints
* expensive search
* async job creation
* file upload
* export/import
* AI/ML calls
* public APIs
* webhook receivers

## Production review checklist

Before merging a DRF endpoint, check:

* Does it require authentication by default?
* Are permissions explicit?
* Are object lookups scoped?
* Does list visibility match detail visibility?
* Are input and output serializers explicit enough?
* Are server-owned fields protected?
* Is business logic outside the view/serializer?
* Are database invariants enforced with constraints when needed?
* Are common filters indexed?
* Are list endpoints paginated?
* Are relations optimized to avoid N+1?
* Are async operations returning 202?
* Are side effects outside transactions when appropriate?
* Are API tests covering user A vs user B?
* Is schema accurate for frontend/client usage?