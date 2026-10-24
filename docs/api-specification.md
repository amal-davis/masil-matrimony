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

### `POST /auth/register/` — create an unverified member account and draft profile (public, throttled)

```json
// request
{"email": "member@example.com", "password": "…", "phone_number": "+919876543210", "accept_terms": true,
 "created_for": "self", "display_name": "Anjali Menon", "gender": "female", "date_of_birth": "2000-01-01"}
// 201 — no tokens: the member verifies their email, then signs in
{"detail": "Check your email. …", "email": "member@example.com", "email_sent": true}
// 400 — field errors, e.g. a taken mobile number, a weak password, or under the minimum age
{"phone_number": ["An account already uses this mobile number. …"], "password": ["This password is too common."]}
// 503 — email can't be sent at all (EMAIL_PROVIDER unset), so no account is created
{"detail": "…", "code": "email_unavailable"}
```

One password field (no confirmation; the website offers show/hide). The password goes through
`AUTH_PASSWORD_VALIDATORS`, including similarity to the email and name. The profile fields use the
dashboard's `CreateProfileSerializer` rules (name format, minimum age 18 for women / 21 for men), and
the profile starts as a `draft` for the member to complete and submit for review.

The account starts unverified and a verification link is emailed
(apps/accounts/email_verification.py). `email_sent: false` means the account exists but the email
couldn't be handed to the mail server; the member can resend. **A registered email gets the same 201
answer**: the details typed are discarded, and only the address's owner is emailed (a new link if
unverified, an "already have an account" note if verified), so the form doesn't reveal registered
addresses. A taken mobile number with a new email is still reported on the field;
`API_THROTTLE_REGISTER` (`10/hour` per IP) limits probing. Mobile numbers are not verified at registration.

### Email verification (public, throttled)

| Endpoint | Behaviour |
|----------|-----------|
| `POST /auth/email/verify/` `{"token"}` | Verifies the account the emailed link belongs to. `200`; `410 verification_link_expired` (after `EMAIL_VERIFICATION_TIMEOUT_SECONDS`, 24 h); `410 email_already_verified` (spent link); `400 verification_link_invalid` (tampered, superseded by a newer link, or the address changed). Signs nobody in. Throttle `API_THROTTLE_EMAIL_VERIFY`. |
| `POST /auth/email/resend/` `{"email"}` | New link to an unverified member, superseding earlier ones. The same `202` for unknown, verified, staff and suspended addresses (which get nothing). `429 verification_rate_limited` after `EMAIL_VERIFICATION_MAX_PER_HOUR` (3) per address, counted for every address; `503` when the email couldn't be sent. Throttle `API_THROTTLE_EMAIL_RESEND`. |
| `POST /auth/email/change/` `{"email", "password", "new_email"}` | Corrects the address of an account that isn't verified yet, proven by its password (failures count toward the sign-in lock), and sends a link to the new address. `400 invalid_credentials`, `403 email_change_not_allowed` (already verified), `409 email_taken`. Throttle `API_THROTTLE_EMAIL_CHANGE`. |

Links look like `{FRONTEND_URL}/verify-email#token=…`: the token is in the fragment, so browsers never
send it to a server. Unverified members are refused everywhere else: `/auth/login/` and
`/auth/otp/verify/` answer `403 email_not_verified` (only after the right password or code),
`/auth/token/` and `/auth/token/refresh/` refuse them (`SIMPLE_JWT["USER_AUTHENTICATION_RULE"]`), and
every member API answers `403 {"code": "email_not_verified"}`. `is_active` remains the separate
suspension switch.

### `POST /auth/login/` — website sign-in with email and password (public, throttled)

Members only (`role=member`, active, with a usable password). The website's Server Action calls
this; mobile apps and staff tools use `/auth/token/` below. The email is trimmed and lower-cased
the way `accounts.User` stores it, and the password is checked by Django's `ModelBackend`.

```json
// request
{"email": "member@example.com", "password": "…"}
// 200
{"access": "<jwt>", "refresh": "<jwt>"}
// 400 — the same for a wrong password, unknown email, staff, inactive or password-less account
{"detail": "The email address or password is incorrect.", "code": "invalid_credentials"}
// 403 — right password, but the email address isn't verified yet
{"detail": "Please verify your email address before signing in. …", "code": "email_not_verified"}
// 429 — too many failures for this address (Retry-After header too)
{"detail": "Too many unsuccessful sign-in attempts. …", "code": "login_rate_limited", "retry_after": 600}
```

- Per address: `LOGIN_MAX_FAILURES` (10) failures per `LOGIN_FAILURE_WINDOW_SECONDS` (900) lock it
  until the oldest failure leaves the window, even for the right password. Counted in MySQL
  (`accounts_authattempt`, keyed by an HMAC of the address, not the address itself). Unknown
  addresses lock the same way. A successful sign-in or password reset clears the count.
- Per IP: `API_THROTTLE_LOGIN` (`20/hour`). Malformed input is a `400` with field errors.

### `POST /auth/password/reset/` — email a password-reset link (public, throttled)

Also how members who joined with SMS login (and have no password) set their first one.

```json
// request
{"email": "member@example.com"}
// 202 — identical whether or not the address belongs to an active member (no email is sent if not)
{"detail": "If an account uses this email address, we've sent it a link to set a new password."}
// 429 — PASSWORD_RESET_MAX_PER_HOUR (3) requests for this address, registered or not
{"detail": "…", "code": "password_reset_rate_limited", "retry_after": 1800}
// 503 — email isn't configured (EMAIL_PROVIDER, DEFAULT_FROM_EMAIL, FRONTEND_URL)
{"detail": "…", "code": "password_reset_unavailable"}
```

The emailed link is `{FRONTEND_URL}/reset-password#uid=<user public_id>&token=<token>`. The token
comes from Django's `default_token_generator`: it expires after `PASSWORD_RESET_TIMEOUT_SECONDS`
(3600) and stops working once the password changes (so it is single-use) or the member signs in.
It is in the URL fragment so it never reaches server logs or `Referer` headers. Per IP:
`API_THROTTLE_PASSWORD_RESET` (`10/hour`).

### `POST /auth/password/reset/confirm/` — set the new password (public, throttled)

```json
// request
{"uid": "<uuid>", "token": "<token>", "new_password": "…", "new_password_confirm": "…"}
// 200
{"detail": "Your password has been changed. You can now sign in."}
// 400 — invalid, expired or used link
{"detail": "This password reset link is invalid or has expired. …", "code": "reset_link_invalid"}
// 400 — AUTH_PASSWORD_VALIDATORS failed, or the two passwords differ
{"new_password": ["This password is too common."]}
```

On success the password is hashed with Django's hasher, `email_verified_at` is set if empty, every
refresh token of the member is blacklisted (signed out everywhere; access tokens still expire
within their lifetime), and a "password changed" email is sent. Per IP:
`API_THROTTLE_PASSWORD_RESET_CONFIRM` (`20/hour`).

### `POST /auth/token/` — obtain tokens (public, throttled)

Any role (mobile apps, API clients). The website uses `/auth/login/` instead.

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

### `POST /auth/otp/request/` — send an SMS login code (public, throttled)

Kept for API clients; the website no longer uses SMS login (members sign in with email and
password). Members only (`role=member`, active). Staff sign in with email and password. Indian mobile
numbers only: `+91` followed by 10 digits starting with 6–9.

```json
// request: E.164 Indian mobile number
{"phone_number": "+919876543210"}
// 202 — identical whether or not the number is registered (no SMS is sent if it isn't)
{"challenge_id": "<uuid>", "code_length": 6, "expires_in": 300, "resend_after": 60}
// 400
{"phone_number": ["Enter an Indian mobile number in international format, e.g. +919876543210."]}
// 429 (also sets Retry-After)
{"detail": "Please wait before requesting another code.", "code": "otp_rate_limited", "retry_after": 42}
// 503 — no SMS provider configured (code "otp_unavailable") or the provider refused (code "otp_delivery_failed")
{"detail": "…", "code": "otp_unavailable"}
```

- Per number: `OTP_RESEND_COOLDOWN_SECONDS` (60) between codes and `OTP_MAX_REQUESTS_PER_HOUR` (5).
  Per IP: `API_THROTTLE_OTP_REQUEST` (`10/hour`).
- A new code invalidates any earlier unused code for the number. The code is never returned.

### `POST /auth/otp/verify/` — exchange the code for tokens (public, throttled)

```json
// request
{"challenge_id": "<uuid>", "code": "123456"}
// 200 — same token pair as /auth/token/; marks the phone number verified
{"access": "<jwt>", "refresh": "<jwt>"}
// 400 — `code` is one of the values below
{"detail": "That code is incorrect.", "code": "otp_incorrect", "attempts_remaining": 4}
```

| `code` | Meaning | Can the same challenge be retried? |
|--------|---------|------------------------------------|
| `otp_incorrect` | Wrong code (always, for unregistered numbers) | Yes, until attempts run out |
| `otp_expired` | Older than `OTP_TTL_SECONDS` (300) | No |
| `otp_used` | Already used to sign in | No |
| `otp_attempts_exceeded` | `OTP_MAX_VERIFY_ATTEMPTS` (5) wrong guesses | No |
| `otp_invalid` | Unknown or superseded challenge, or the account changed | No |

Per IP: `API_THROTTLE_OTP_VERIFY` (`20/hour`). Malformed input (`400` with field errors) is not
counted as a guess.

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

### Member endpoints (member dashboard)

All require a member's access token (`role=member`; staff get `403`). The acting member is always
taken from the token, never from the request body. Lists are paginated (`?page=`, 20 per page:
`{"count", "next", "previous", "results"}`). Endpoints that need the member's own profile answer
`404 {"detail": "...", "code": "no_profile"}` until it is created. Rule violations answer
`409 {"detail": "...", "code": "..."}` with a message safe to show.

| Method and path | Purpose |
|-----------------|---------|
| `GET /dashboard/summary/` | Overview: profile status and completion, membership, interest counts, shortlist count, recent interests and notifications. All counts come from stored records. |
| `GET /profiles/me/` · `POST` · `PATCH` | Own profile (all fields, raw choice values). `POST` creates it (`created_for`, `display_name`, `gender`, `date_of_birth` required; minimum age 18 for brides, 21 for grooms). `PATCH` updates only the fields sent. `display_name`, `gender` and `date_of_birth` can't change once submitted. |
| `PATCH /profiles/me/partner-preference/` | Partner preferences (age and height ranges, marital statuses, religions, communities, free-text locations, education, occupation, notes). |
| `POST /profiles/me/submit/` | Submit a complete draft (or a profile returned for changes) for staff review. `409 incomplete` lists what's missing. |
| `GET /profiles/me/photos/` · `POST` (multipart `photo`) | Own photos with review status / upload one. JPEG, PNG or WebP, decoded and re-encoded server-side, at most `PROFILE_PHOTO_MAX_BYTES` (8 MB) and `PROFILE_MAX_PHOTOS` (10) per profile. Throttle `API_THROTTLE_PHOTO_UPLOAD`. |
| `DELETE /profiles/me/photos/{id}/` · `POST …/primary/` | Remove a photo / make it the main photo. Another member's photo id is `404`. |
| `GET /profiles/photo-files/{token}/` | The image file for a signed URL that expires after `PHOTO_URL_TTL_SECONDS`. Photo URLs in every response are of this form; files are never publicly listed. |
| `GET /profiles/matches/` | Approved, visible profiles of the opposite gender matching the member's partner preferences, newest first. No compatibility scoring. |
| `GET /profiles/{code}/` | Another member's profile, privacy-filtered (age, never date of birth; no contact details; income only if the member chose to show it; photos per their photo privacy), plus the viewer's interest and shortlist state. Hidden/unapproved profiles are `404`. |
| `POST /interests/` `{"profile_code"}` | Send an interest. Needs an approved own profile (`403 profile_not_active`); one per pair (`409 duplicate`); `409 reverse_exists` if they already sent you one. Members without a current paid subscription are on the Free package: `403 interest_limit_reached` once they have sent its `outgoing_interest_limit` (15) interests in total, one per member, no reset; re-sending a withdrawn interest doesn't count again. Throttle `API_THROTTLE_INTEREST_SEND`. |
| `GET /interests/received/` · `GET /interests/sent/` (`?status=pending\|accepted\|declined\|withdrawn`) | Interests by direction. |
| `POST /interests/{id}/accept/` · `…/decline/` | Receiver only, pending only (`409 not_pending` otherwise). Notifies the sender. |
| `POST /interests/{id}/withdraw/` | Sender only, pending only. A withdrawn interest can be sent again. |
| `GET /shortlist/` · `POST /shortlist/` `{"profile_code"}` · `DELETE /shortlist/{code}/` | Shortlist; adding twice is harmless. |
| `GET /profiles/{code}/contact/` · `POST` | GET: whether the viewer may see the member's mobile number (`access`: `available`, `viewed`, `not_included`, `not_shared`, `limit_reached`, `profile_not_active`, `no_number`, with `limit`/`used`); never the number. POST: returns `phone_number`, using one of the current subscription's contact views unless this member was already viewed during it (limits count different members per subscription). Needs a current Silver/Gold/Diamond subscription and the member's consent (`contact_sharing = paid_members`); otherwise `403` with the access code. Throttle `API_THROTTLE_CONTACT_VIEW` (POST). |
| `GET /memberships/packages/` | Public. The available packages in display order: fee and `fee_label`, `tax_treatment` (`no_fee`, `gst_extra`, `gst_stated`), `stated_gst_rate`, `gst_amount` and `total_payable` (both `null` when GST is extra at the applicable rate), `validity_months`, `contact_view_limit`, `outgoing_interest_limit`, benefits and terms copy. Money is a decimal string. |
| `GET /memberships/me/` | Current subscription (or `null`) with the fee, validity and contact limit stored when it was recorded, history, `entitlements` (the package in force and its interest/contact limits; Free when there is no current subscription), and `online_payment_available` (always `false` until a payment gateway is integrated). |
| `GET /notifications/` (`?unread=1`) · `POST /notifications/{id}/read/` · `POST /notifications/read-all/` | In-app notifications, with `unread_count`. |

### Development-only: `GET /schema/`, `GET /docs/`
Available when `API_DOCS_ENABLED=True` (default in development, off in production).

## 3. Planned endpoints (not implemented)

Indicative only; finalised per module.

| Area | Endpoints | Access |
|------|-----------|--------|
| Search | `GET /profiles/search/?age_min=&age_max=&religion=&location=…` | Member (limited public preview) |
| Blocks / reports / profile views | `/blocks/`, `/reports/`, `/profile-views/` | Member |
| Payments | `POST /payments/orders/`, `POST /payments/webhooks/{gateway}/` | Member / gateway (signature-verified) |
| Verification queue | `/staff/verification/profiles/`, `…/{id}/approve/` | Verification staff |
| CRM | `/crm/leads/`, `/crm/leads/{id}/calls/`, `/crm/follow-ups/` | Telecaller (own leads), manager (team) |
| Content | `/content/pages/{slug}/` (public), `/staff/content/...` | Public / Content manager |
| Audit | `GET /staff/audit-logs/` | Super admin, admin |
