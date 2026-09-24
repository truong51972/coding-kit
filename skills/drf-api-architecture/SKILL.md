---
name: drf-api-architecture
description: Design, review, and refactor production Django REST Framework APIs with thin API layers, explicit serializers, scoped object access, workflow boundaries, async job triggers, and testable contracts.
---

# DRF API Architecture

Use this skill for production Django REST Framework APIs where DRF acts as the application API boundary for resource management, authorization, workflow commands, and database-backed state.

This skill is general-purpose. It is not tied to any specific project.

## When to use

Use this skill when working on:

- DRF endpoint design or refactor
- serializers for create/update/list/detail/command operations
- permissions, ownership, multi-tenant access, or object visibility
- QuerySet, Manager, model, selector, or object-access patterns
- service-layer boundaries for business workflows
- async job-triggering endpoints
- API tests, schema, pagination, throttling, and error shape
- reducing fat views, fat serializers, or unsafe object lookup

## When not to use

Do not use this skill as the main guide for:

- pure Django template views
- FastAPI services
- Celery worker implementation details
- database schema design unrelated to API behavior
- authentication provider design
- frontend API consumption

Use a more specific skill when the task is mostly about those areas.

## Core stance

DRF is the API boundary, not the business logic layer.

Prefer:

- thin views
- explicit serializers
- scoped QuerySets
- service functions for writes/workflows
- selectors or QuerySet methods for reads
- model constraints for durable invariants
- tests for auth, permission, object access, and response contracts

Avoid:

- large workflows inside views
- business side effects inside serializers
- unscoped object lookups
- exposing model internals directly
- generic ViewSets for complex command-heavy APIs
- inconsistent response/error shapes

## Reference map

Read only the references needed for the task.

- `references/architecture.md`
  - Use when deciding app structure, service/selector boundaries, or where code should live.
- `references/api-layer.md`
  - Use when choosing APIView, GenericAPIView, generic views, ViewSet, ModelViewSet, routing, pagination, filtering, and response shape.
- `references/serializers.md`
  - Use when designing input/output serializers, validation, nested serializers, model serializers, and command serializers.
- `references/model-queryset-object-access.md`
  - Use when reviewing models, QuerySets, Managers, ownership filters, object access, soft delete, constraints, indexes, transactions, and query optimization.
- `references/async-jobs.md`
  - Use when an API endpoint triggers background processing, long-running work, state transitions, or external side effects.
- `references/testing-schema-security.md`
  - Use when writing tests, reviewing security, defining OpenAPI schema, or checking production readiness.

## Default workflow

When reviewing or implementing a DRF API:

1. Identify the resource or command.
2. Decide whether this is CRUD, read-only, command-style, or async.
3. Choose the smallest suitable DRF primitive.
4. Define input serializer and output serializer separately when useful.
5. Ensure object access is scoped by user/tenant/project/organization before lookup.
6. Move business writes/workflows to services.
7. Move read composition/query optimization to QuerySets or selectors.
8. Add model constraints/indexes for durable invariants.
9. Add tests for auth, permissions, ownership, validation, success response, and failure response.
10. Add or update OpenAPI schema annotations for non-trivial endpoints.

## Output expectations

When producing code, include:

- the view
- serializers
- service/selector if needed
- permission/object-access pattern
- urls/router entry
- tests or test checklist
- schema annotations when useful

When reviewing code, report:

- correctness risks
- security/authorization risks
- query/performance risks
- API contract issues
- layering issues
- suggested patch direction