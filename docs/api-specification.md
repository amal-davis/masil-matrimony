# API Specification

Base URL (development): `http://127.0.0.1:8000/api/v1`

The live, code-generated reference is available in development at:

- Swagger UI: `http://127.0.0.1:8000/api/v1/docs/`
- OpenAPI schema: `http://127.0.0.1:8000/api/v1/schema/` (YAML; add `?format=json` for JSON)

This document defines the conventions every endpoint follows, plus the endpoints implemented so far.

## 1. Conventions

### Versioning
- All endpoints live under `/api/v1/`. Breaking changes go into `/api/v2/` while v1 keeps working
  for existing mobile app versions.
- Non-breaking additions (new fields, new endpoints) are made in place.

### Format
- Requests and responses are JSON (`Content-Type: application/json`). File uploads (future) use
  `multipart/form-data` on dedicated endpoints.
- Field names are `snake_case`. Timestamps are ISO 8601 in UTC (e.g. `2026-10-14T10:30:00Z`).
- Resources are identified by UUID `id` values (the model's `public_id`); internal numeric keys are
  never exposed.

### Authentication
- Mobile apps and server-side web code: `Authorization: Bearer <access_token>`.
- Django admin / browsable API: session cookie + CSRF token.
- Every endpoint requires authentication unless documented as public.
- See [architecture.md](architecture.md#4-authentication-and-authorisation) for the browser cookie strategy.

### Authorisation
- Role checks are enforced by the API. A request that is authenticated but not allowed returns `403`.
- List endpoints only return objects the caller may see (filtered querysets), not just hidden UI.

### Errors

| Status | Meaning | Body |
|--------|---------|------|
| 400 | Validation error | `{"field_name": ["message", ...], "non_field_errors": [...]}` |
| 401 | Missing/invalid/expired credentials | `{"detail": "..."}` (expired tokens also include `"code": "token_not_valid"`) |
| 403 | Authenticated but not permitted | `{"detail": "..."}` |
| 404 | Not found (also used to avoid revealing private resources) | `{"detail": "Not found."}` |
| 405 | Method not allowed | `{"detail": "..."}` |
| 429 | Rate limit exceeded | `{"detail": "Request was throttled. Expected available in N seconds."}` |
| 500 | Unexpected error (details logged server-side only) | `{"detail": "An unexpected error occurred. Please try again later."}` |
| 503 | Dependency unavailable (readiness check) | see below |

### Pagination
List endpoints use page-number pagination (default 20 per page):

```json
{ "count": 125, "next": "…?page=3", "previous": "…?page=1", "results": [ … ] }
```

### Rate limiting
Defaults (configurable via environment): anonymous 60/min, authenticated 300/min, auth endpoints
10/min. Responses over the limit return `429` with a `Retry-After` header.

### Privacy rules for profile data (binding for future endpoints)
- Public/anonymous endpoints never return contact details, exact date of birth, documents, private
  photos, or the owner's account email/phone.
- Member-to-member endpoints return contact details only when the viewer is entitled
  (membership quota, accepted interest, owner's privacy settings), and each reveal is recorded.
- Staff endpoints that expose private data are role-restricted and write an audit log entry.

## 2. Implemented endpoints

### `GET /health/` — liveness (public)

The API process is running. Does not touch the database.

```http
HTTP/1.1 200 OK
{"status": "ok", "service": "matrimony-api", "api_version": "v1"}
```

### `GET /health/ready/` — readiness (public)

The API can query its database. Use for load-balancer/orchestrator readiness probes.

```http
HTTP/1.1 200 OK
{"status": "ok", "service": "matrimony-api", "api_version": "v1"}
```
```http
HTTP/1.1 503 Service Unavailable
{"status": "unavailable", "service": "matrimony-api", "api_version": "v1"}
```

Neither endpoint returns configuration, versions of server software, hostnames or error details.

### `POST /auth/token/` — obtain tokens (public, throttled)

```json
// request
{"email": "member@example.com", "password": "…"}
// 200
{"access": "<jwt>", "refresh": "<jwt>"}
// 401 for wrong credentials or inactive account
{"detail": "No active account found with the given credentials"}
```

### `POST /auth/token/refresh/` — rotate tokens (public, throttled)

```json
// request
{"refresh": "<jwt>"}
// 200 — a new pair; the submitted refresh token is blacklisted
{"access": "<jwt>", "refresh": "<jwt>"}
```
Reusing a refresh token that was already rotated returns `401`.

### `POST /auth/token/blacklist/` — logout (public, throttled)

```json
// request
{"refresh": "<jwt>"}
// 200
{}
```

### `GET /auth/me/` — current user (authenticated)

```json
{
  "id": "6f1c2b9e-0c55-4c43-9d6e-7c3a3e7f6b10",
  "email": "member@example.com",
  "phone_number": "+919876543210",
  "first_name": "Anu",
  "last_name": "K",
  "role": "member",
  "email_verified_at": null,
  "phone_verified_at": "2026-10-14T10:30:00Z",
  "date_joined": "2026-10-01T08:00:00Z"
}
```

### `POST /enquiries/` — contact form (public, throttled)

Stores a message from the website's Contact page as an `Enquiry` (status `new`) for staff to
follow up in the Django admin. No authentication, session or CSRF token is involved. Limited to
`API_THROTTLE_ENQUIRIES` per IP address (default `5/hour`) and 16 KB per request.

```json
// request
{"name": "Anu Thomas", "email": "anu@example.com", "phone": "98765 43210",
 "message": "I'd like to know more about registering.", "website": ""}
// 201 — only the new enquiry's id; nothing the visitor sent is echoed back
{"id": "0b6f1c9e-2d4a-4c1e-9a77-5f3e2b1d8c40"}
// 400
{"phone": ["Enter a valid phone number, e.g. +91 98765 43210."]}
```

- `name` 2–100 characters (letters in any script, spaces, `.` `'` `-`); `email` up to 254;
  `message` 10–2000 characters after trimming.
- `phone` accepts `+<country code>…`, `00<country code>…`, a 10-digit Indian mobile or an Indian
  number with a leading `0`; it is stored in E.164 form (`+919876543210`).
- `website` is a honeypot hidden from people. If it is filled in, the response is still `201`
  (with `"id": null`) but nothing is stored.
- Logs record the enquiry id only, never the visitor's details or message.

### Development-only: `GET /schema/`, `GET /docs/`
Available when `API_DOCS_ENABLED=True` (default in development, off in production).

## 3. Planned endpoints (not implemented)

Indicative only; finalised per module.

| Area | Endpoints | Access |
|------|-----------|--------|
| Registration / OTP | `POST /auth/register/`, `POST /auth/otp/request/`, `POST /auth/otp/verify/`, password reset | Public, throttled |
| Own profile | `GET/PATCH /profiles/me/`, photos, preferences, privacy settings | Member |
| Search | `GET /profiles/search/?age_min=&age_max=&religion=&location=…` | Member (limited public preview) |
| Profile detail | `GET /profiles/{id}/` (privacy-filtered) | Member |
| Interests | `POST /interests/`, `POST /interests/{id}/accept/`, `…/decline/` | Member |
| Shortlist / blocks / reports | `/shortlists/`, `/blocks/`, `/reports/` | Member |
| Memberships | `GET /memberships/plans/`, `GET /memberships/me/` | Public / Member |
| Payments | `POST /payments/orders/`, `POST /payments/webhooks/{gateway}/` | Member / gateway (signature-verified) |
| Notifications | `GET /notifications/`, `POST /notifications/{id}/read/` | Member |
| Verification queue | `/staff/verification/profiles/`, `…/{id}/approve/` | Verification staff |
| CRM | `/crm/leads/`, `/crm/leads/{id}/calls/`, `/crm/follow-ups/` | Telecaller (own leads), manager (team) |
| Content | `/content/pages/{slug}/` (public), `/staff/content/...` | Public / Content manager |
| Audit | `GET /staff/audit-logs/` | Super admin, admin |
