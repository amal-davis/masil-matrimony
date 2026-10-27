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

### Member authentication: SMS one-time codes

Members register and log in with a one-time code sent by SMS to their mobile number. There is no
member password and no email verification; email is optional contact information. Staff keep
email + password (Django admin and `/auth/token/`). Codes are generated and checked by this API
(`apps/accounts/otp.py`, only a keyed hash is stored); the SMS provider only delivers them.

Mobile numbers may be sent in any common written form (`"+91 98765 43210"`, `"0091 9876543210"`)
and are normalised to E.164 (`+919876543210`). Only countries in `SMS_ALLOWED_COUNTRY_CODES`
(default `91`) are accepted; Indian numbers must be mobiles (10 digits starting 6–9).

Limits, shared by registration and login for the same number: `OTP_RESEND_COOLDOWN_SECONDS` (60)
between codes, `OTP_MAX_REQUESTS_PER_HOUR` (5) and `OTP_MAX_REQUESTS_PER_DAY` (10) per number,
`OTP_TTL_SECONDS` (300) per code, `OTP_MAX_VERIFY_ATTEMPTS` (5) wrong guesses per code. A new code
invalidates any earlier one for the number. Per IP: `API_THROTTLE_REGISTER`, `API_THROTTLE_OTP_REQUEST`
(`10/hour`), `API_THROTTLE_OTP_VERIFY` (`20/hour`).

Every endpoint that sends a code answers `202` with:

```json
{"challenge_id": "<uuid>", "phone_number": "+919876543210", "code_length": 6, "expires_in": 300, "resend_after": 60}
```

and may fail with `429 {"code": "otp_rate_limited", "retry_after": 42}` (also a `Retry-After`
header), `503 {"code": "otp_unavailable"}` (no `SMS_PROVIDER`) or `503 {"code": "otp_delivery_failed"}`
(the provider didn't accept the message; nothing is kept, so retrying immediately is allowed).

### `POST /auth/register/` — start a registration (public, throttled)

```json
// request (email required: payment receipts are sent there)
{"phone_number": "+919876543210", "email": "member@example.com", "accept_terms": true,
 "created_for": "self", "display_name": "Anu K", "gender": "female", "date_of_birth": "1998-05-01"}
// 202 — code sent; no account exists yet
// 400 — field errors (profile rules, minimum age, invalid number, email used by another account)
// 409 — the number already has an account: log in instead
{"detail": "An account already uses this mobile number. Please log in instead.", "code": "phone_registered",
 "phone_number": ["…"]}
```

The validated details are kept on the code's challenge (`PhoneOTPChallenge.registration`). If the
code is never entered, no account is ever created; `purge_otp_challenges` deletes the details a day
after the code expires. Saying a number is taken lets people probe numbers; the per-IP throttle limits that.

### `POST /auth/register/resend/` — new registration code (public, throttled)

`{"challenge_id": "<uuid>", "phone_number": "+91…" (optional)}`. Sends a new code for the same
registration, optionally to a corrected number, without the details being sent again. `202`; `409
phone_registered` for a corrected number that has an account; `410 registration_expired` when the
registration was completed, is unknown, or its last code is older than `OTP_REGISTRATION_WINDOW_SECONDS` (3600).

### `POST /auth/register/verify/` — complete the registration (public, throttled)

```json
// request
{"challenge_id": "<uuid>", "code": "123456"}
// 201 — account (mobile verified, unusable password) and draft profile created; signed in
{"access": "<jwt>", "refresh": "<jwt>"}
// 400 — the code errors in the table below
// 409 — phone_registered / email_taken: another account took the number or address meanwhile
```

### `POST /auth/otp/request/` — send a login code (public, throttled)

`{"phone_number": "+919876543210"}`. Members only (`role=member`, active). The `202` is identical
whether or not the number has an eligible account; for others no SMS is sent and the challenge can
never verify, so the endpoint doesn't reveal which numbers are registered. Never creates an account.

### `POST /auth/otp/verify/` — exchange the code for tokens (public, throttled)

```json
// request
{"challenge_id": "<uuid>", "code": "123456"}
// 200 — token pair; marks the mobile number verified if it wasn't (legacy accounts)
{"access": "<jwt>", "refresh": "<jwt>"}
// 400
{"detail": "That code is incorrect.", "code": "otp_incorrect", "attempts_remaining": 4}
```

| `code` | Meaning | Can the same challenge be retried? |
|--------|---------|------------------------------------|
| `otp_incorrect` | Wrong code (always, for unregistered numbers at login) | Yes, until attempts run out |
| `otp_expired` | Older than `OTP_TTL_SECONDS` (300) | No |
| `otp_used` | Already used | No |
| `otp_attempts_exceeded` | `OTP_MAX_VERIFY_ATTEMPTS` (5) wrong guesses | No |
| `otp_invalid` | Unknown, superseded or wrong-purpose challenge, or the account changed (suspended, number changed) | No |

Malformed input (`400` with field errors) is not counted as a guess. A login code can't complete a
registration and vice versa.

### Mobile verification gate

Members whose `phone_verified_at` is empty can't use the site: `/auth/token/refresh/` refuses them
(`SIMPLE_JWT["USER_AUTHENTICATION_RULE"]`) and member APIs answer `403 {"code": "phone_not_verified"}`.
A successful SMS login sets it. Changing a member's number clears it. `is_active` remains the
separate suspension switch. Email verification no longer gates anything.

### `POST /auth/token/` — obtain tokens with email + password (staff only, throttled)

For staff API clients. Members get the same `401` as a wrong password, even if they still have a
password from the old email sign-in.

```json
// request
{"email": "staff@example.com", "password": "…"}
// 200
{"access": "<jwt>", "refresh": "<jwt>"}
```

Removed: `/auth/login/`, `/auth/password/reset/`, `/auth/password/reset/confirm/`,
`/auth/email/verify/`, `/auth/email/resend/`, `/auth/email/change/` (`404`).

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
| `PATCH /profiles/me/partner-preference/` | Partner preferences: age and height ranges; lists of marital statuses, religions, communities, mother tongues, diets; comma-separated locations, education, occupation; notes; `must_haves` (criterion keys `age`, `height`, `marital_status`, `religion`, `community`, `mother_tongue`, `location`, `education`, `occupation`, `diet`). Matches use the saved values on the next request. |
| `POST /profiles/me/submit/` | Submit a complete draft (or a profile returned for changes) for staff review. `409 incomplete` lists what's missing. |
| `GET /profiles/me/photos/` · `POST` (multipart `photo`) | Own photos with review status / upload one. JPEG, PNG or WebP, decoded and re-encoded server-side, at most `PROFILE_PHOTO_MAX_BYTES` (8 MB) and `PROFILE_MAX_PHOTOS` (10) per profile. Throttle `API_THROTTLE_PHOTO_UPLOAD`. |
| `DELETE /profiles/me/photos/{id}/` · `POST …/primary/` | Remove a photo / make it the main photo. Another member's photo id is `404`. |
| `GET /profiles/photo-files/{token}/` | The image file for a signed URL that expires after `PHOTO_URL_TTL_SECONDS`. Photo URLs in every response are of this form; files are never publicly listed. |
| `GET /profiles/highlighted/` | **Public** (no sign-in). The homepage's Highlighted Profiles: approved, visible profiles that staff highlighted in the admin (`is_highlighted`, needs the "Can highlight profiles on the homepage" permission) **and** whose member agreed to be featured (`homepage_consent`, Privacy settings). At most 12 (`?limit=` for fewer), ordered by `highlight_order`, newest approval, newest profile. Each card: `profile_code`, `given_name` (first word of the name only), `gender`, `age`, `education`, `location {city, district, state}`, `photo` (main approved photo only when the member's photos are visible to all members, else null). Uncached. |
| `GET /profiles/matches/` | The member's matches (`apps/profiles/matching.py`): approved, visible, active profiles of the opposite gender that meet every filled-in must-have, best score first (ties: most recently approved). Each card adds `match: {score (0-100, or null with no preferences), reasons, not_stated, mutual}`; the page adds `preferences_set` and `mutual_only`. `?mutual=1` keeps only profiles whose own must-haves the member meets. Never returns the other member's preferences, contact details or date of birth. |
| `GET /profiles/search/` | Member search by the filters given (`apps/profiles/search.py`), with `advanced_search` (whether the plan includes advanced filters). Basic filters (gender, age, height, religion, caste, location, Matrimony ID) are for every member; `marital_status`, `mother_tongue`, `education` and `occupation` need Silver/Gold/Diamond, otherwise `403 upgrade_required` with the `filters` used. Results that match are ordered with Priority Profile Visibility (Gold/Diamond, `apps/profiles/priority.py`) first, then most recently approved. Match suggestions use priority only between equal match points. |
| `GET /profiles/{code}/` | Another member's profile, privacy-filtered (age, never date of birth; no contact details; income only if the member chose to show it; photos per their photo privacy), plus the viewer's interest and shortlist state. Hidden/unapproved profiles are `404`. |
| `POST /interests/` `{"profile_code"}` | Send an interest. Needs an approved own profile (`403 profile_not_active`); one per pair (`409 duplicate`); `409 reverse_exists` if they already sent you one. Members without a current paid subscription are on the Free package: `403 interest_limit_reached` once they have sent its `outgoing_interest_limit` (15) interests in total, one per member, no reset; re-sending a withdrawn interest doesn't count again. Throttle `API_THROTTLE_INTEREST_SEND`. |
| `GET /interests/received/` · `GET /interests/sent/` (`?status=pending\|accepted\|declined\|withdrawn`) | Interests by direction. |
| `POST /interests/{id}/accept/` · `…/decline/` | Receiver only, pending only (`409 not_pending` otherwise). Notifies the sender. |
| `POST /interests/{id}/withdraw/` | Sender only, pending only. A withdrawn interest can be sent again. |
| `GET /shortlist/` · `POST /shortlist/` `{"profile_code"}` · `DELETE /shortlist/{code}/` | Shortlist; adding twice is harmless. |
| `GET /profiles/{code}/contact/` · `POST` | GET: whether the viewer may see the member's mobile number (`access`: `available`, `viewed`, `not_included`, `not_shared`, `same_gender`, `limit_reached`, `profile_not_active`, `no_number`, with `limit`/`used`); never the number. POST: returns `phone_number`, using one of the current subscription's contact views unless this member was already viewed during it (limits count different members per subscription). Needs a current Silver/Gold/Diamond subscription and the member's consent (`contact_sharing = paid_members`); otherwise `403` with the access code. Throttle `API_THROTTLE_CONTACT_VIEW` (POST). |
| `GET /messages/` | The member's conversations, latest first: the other member's card (or a stub once unavailable), the last message and `unread`. Never another member's conversations. |
| `GET /messages/{code}/` · `POST` `{"body"}` | The conversation with one member (newest first, paginated; page 1 marks their messages read) and `messaging` (`can_send`, `code`: `available`, `interest_required`, `upgrade_required`, `unavailable`, `profile_not_active`). POST sends a message (1–2000 characters). Needs an approved own profile, a discoverable opposite-gender recipient and an accepted interest either way; starting a conversation needs messaging in the plan (Silver/Gold/Diamond), replying doesn't (`apps/interactions/messaging.py`). Throttle `API_THROTTLE_MESSAGE_SEND` (POST). |
| `GET /profile-views/` | Members who opened the member's profile page, most recent first, with `visits` and `last_viewed_at` (`apps/interactions/profile_views.py`). Needs "who viewed my profile" in the plan; otherwise `403 upgrade_required` with `viewer_count` only. Hidden or unapproved viewers aren't listed. |
| `POST /profiles/me/verification/` | Ask staff to verify the member's identity for the Verified badge. Needs the badge in the plan (`403 upgrade_required`), an approved profile and a verified mobile number; `409 already_requested` / `already_verified`. Only staff decide (admin actions); cards carry `verified: true` once they do. |
| `GET /memberships/packages/` | Public. The available packages in display order: fee and `fee_label`, `tax_treatment` (`no_fee`, `gst_extra`, `gst_stated`), `stated_gst_rate`, `gst_amount` and `total_payable` (both `null` when GST is extra at the applicable rate), `validity_months`, `contact_view_limit`, `outgoing_interest_limit`, benefits and terms copy. Money is a decimal string. |
| `GET/POST /memberships/me/assistance/` | Matchmaking assistance (`apps/memberships/assistance.py`). GET: `included`, `available` and the member's `requests` (status, `assigned`, `matchmaker_name` once staff assigned someone, staff `message`). POST `{note}`: `201`; `403 upgrade_required` (not Gold/Diamond), `403 service_unavailable` (`MATCHMAKING_ASSISTANCE_AVAILABLE` off), `403 profile_not_active`, `409 already_requested`. Staff assign and progress requests in the admin. |
| `POST /profiles/matches/<profile_code>/hide/` | Hide a suggested profile from the signed-in member's own matches (`204`; `404` for their own or a non-visible profile). `GET /profiles/matches/` leaves out hidden suggestions and those staff dismissed or flagged; with `MATCH_REVIEW_REQUIRED`, only staff-approved ones. Responses never include review or staff metadata. |
| `GET /memberships/me/assistance/<id>/` | One of the member's own cases (others: `404`): `kind`, status, `matchmaker_name` once assigned, `service_active`, service dates, and only what staff chose to show: `updates`, `follow_ups`, `suggestions` (profile cards), `exchanges`. Never internal notes. |
| `PATCH /memberships/me/assistance/<id>/requirements/` | `{requirements}`: the member's own requirements on their open service case. Staff fields can't be changed. |
| `POST /memberships/me/assistance/<id>/consultations/` | Royal: `{note, address}` requests an at-home consultation (one open at a time; `403` for other cases or after the service period). The address is never returned (`location_provided` only). |
| `POST /memberships/me/assistance/<id>/consultations/<cid>/` | `{action: confirm|cancel}`. Only a staff-proposed time can be confirmed, and only then is it `scheduled`. |
| `POST /memberships/me/assistance/<id>/family/` | Royal: `{name, relationship, phone_number?, purpose, permission: true}` permits coordination with that family member for that purpose (`400` without `permission`). |
| `POST /memberships/me/assistance/<id>/family/<fid>/` | `{decision: grant|withdraw}` on a family contact (e.g. one suggested by staff). Staff record coordination only while granted. Responses show the number's last digits only. |
| `POST /memberships/me/assistance/<id>/suggestions/<profile_code>/` | `{response: interested|not_interested}` on a profile the matchmaker shared. |
| `GET /memberships/contact-exchanges/` | Matchmaker-proposed exchanges of mobile numbers involving the member (either side): purpose, the exact consent `statement`, `my_decision`, status, the other member's card, and `phone_number` only once both consented (showing it is recorded). |
| `POST /memberships/contact-exchanges/<id>/` | `{decision: grant|decline|withdraw}`. Only the two members; `404` otherwise. `409 closed` once no longer pending, `409 service_ended` to grant after the Platinum service period. Decline or withdrawal before both agree ends it with nothing disclosed. |
| `GET /memberships/me/` | Current subscription (or `null`) with the fee, validity and contact limit stored when it was recorded, history, `entitlements` (the package in force, its `features` and interest/contact limits, and `unavailable`: included features switched off platform-wide; Free when there is no current subscription), `assistance` (as GET `/memberships/me/assistance/`), and `online_payment_available` (always `false` until a payment gateway is integrated). |
| `GET /notifications/` (`?unread=1`) · `POST /notifications/{id}/read/` · `POST /notifications/read-all/` | In-app notifications, with `unread_count`. |

### Membership payments (members; see docs/payments.md)

| Endpoint | Purpose |
|---|---|
| `GET /payments/checkout/<package>/` | Price from the package (`base`, `gst_rate`, `gst`, `total`, `currency`), the member's billing details, and `available` / `blocked {code, message}` (`payments_unavailable`, `price_not_confirmed`, `email_required`, `membership_active`, `not_purchasable`). |
| `POST /payments/purchases/` `{"package"}` | Start or resume checkout. `201 {purchase, checkout}`; `checkout` holds the Razorpay key id, order id, amount (paise), currency and prefill. Never an amount from the client. `503 order_failed` when Razorpay refuses (nothing charged). |
| `GET /payments/purchases/` | The member's purchases, newest first (paginated). |
| `GET /payments/purchases/<ref>/` | One purchase; includes `checkout` while it can still be paid. Another member's reference is `404`. |
| `POST /payments/purchases/<ref>/verify/` | Razorpay Checkout's success response. `400 invalid_payment_signature`; `202 {confirmation_pending: true}` if Razorpay can't be asked yet; otherwise the purchase as Razorpay's API confirms it. |
| `POST /payments/purchases/<ref>/refresh/` | Ask Razorpay again ("Check payment status"). |
| `GET /payments/receipts/<uuid>/` | A receipt of one of the member's own purchases. |
| `POST /payments/razorpay/webhook/` | Razorpay only: `X-Razorpay-Signature` over the raw body with the webhook secret. |
| `PATCH /auth/me/email/` `{"email"}` | The member corrects their own email address (where receipts go). |

Purchase `status`: `awaiting_payment`, `authorized` (not paid), `paid`, `failed`, `needs_review`, `order_failed`.

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
