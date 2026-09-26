# API Reference — Supplementary Guide

Purpose
-------
This file provides human-friendly guidance and usage notes that supplement the auto-generated OpenAPI schema exposed by the running service at `/docs` and `/redoc`. The authoritative, machine-readable contract is the OpenAPI schema generated from the route definitions in `api/v1/router.py`.

How to view the spec
--------------------
- Run the API locally and open `/docs` for the interactive Swagger UI or `/redoc` for the Redoc rendering.
- The OpenAPI JSON/YAML is available from the served endpoint (e.g., `/openapi.json`).

Base URL & Versioning
---------------------
- All current endpoints are versioned under `/api/v1`.
- Backwards-incompatible changes require a new major path (for example, `/api/v2`) and an RFC-style design review.

Authentication
--------------
- The service uses bearer tokens for authenticated requests. Most endpoints expect an `Authorization: Bearer <token>` header.
- For machine-to-machine integrations, use a long-lived or scoped service token as configured by the identity provider.

Common Patterns
---------------
- Content type: `application/json` for request and response bodies unless stated otherwise.
- Pagination: endpoints that return lists use standard cursor or offset-style pagination. Check the individual route schema for exact parameter names (e.g., `limit`, `offset`, `cursor`).
- Filtering & Sorting: use query parameters; supported keys are declared in each endpoint's schema.
- Idempotency: non-idempotent POST operations that can be retried expose idempotency keys via an `Idempotency-Key` header (when applicable).

Error Responses
---------------
- Errors follow a structured JSON shape. Typical fields: `code`, `message`, and `details` (optional). HTTP status codes follow standard semantics (4xx client errors, 5xx server errors).
- For validation errors, the response includes per-field error information. See the endpoint schema for exact shape.

Rate Limits & Quotas
--------------------
- Rate limiting may be enforced per-API key, IP, or tenant. When limited, endpoints return `429 Too Many Requests` and include retry guidance in headers.

Examples
--------
Fetch a list (curl):

```
curl -H "Authorization: Bearer $TOKEN" "https://api.example.com/api/v1/resources?limit=25"
```

Create (curl):

```
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"example"}' "https://api.example.com/api/v1/resources"
```

Extending or Updating the Docs
------------------------------
- The OpenAPI spec is generated from route definitions and model schemas in `api/v1/router.py` and the codebase's API models. To update documentation:
  1. Update route docstrings, parameter annotations, or Pydantic/serializers used by the route.
  2. Run the app locally and verify changes at `/docs` or `/redoc`.
  3. Include any prose changes to this file where human context is useful (examples, migration notes).

Authoritative Source
--------------------
- The canonical API contract is the auto-generated OpenAPI schema produced by the running application. Always consult `/docs` when building clients or integrations.

Change Policy
-------------
- Non-breaking changes may be deployed behind feature flags and announced in release notes.
- Breaking changes require a version bump and migration guidance for integrators.

Revision history
----------------
- Created: initial supplement referencing `api/v1/router.py`.
