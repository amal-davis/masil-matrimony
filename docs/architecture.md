# Architecture

## 1. Overview

```
                ┌──────────────────────────┐
 Browsers ────▶ │  Next.js (frontend/)     │──┐
                │  public site, member     │  │  HTTPS, JSON
                │  portal, admin, CRM UIs  │  │  /api/v1/...
                └──────────────────────────┘  ▼
                                      ┌──────────────────────────┐      ┌─────────┐
 Android / iOS apps ────────────────▶ │ Django REST API          │ ───▶ │  MySQL  │
 (future, same API)    Bearer JWT     │ (backend/)               │      │  8.x    │
                                      └──────────────────────────┘      └─────────┘
```

- **One API, many clients.** All business rules, validation and permission checks live in the
  Django API. The website, staff interfaces and future mobile apps are clients of `/api/v1/`.
- **One database.** MySQL is the only system of record. Schema changes go through Django migrations.
- **The frontend holds no business authority.** Hiding a button in the UI is a convenience, never
  a security control; the API enforces every rule.

## 2. Backend (`backend/`)

```
backend/
  manage.py
  requirements.txt
  .env.example
  config/
    env.py                 environment loading and validation
    settings/base.py       shared settings
    settings/development.py
    settings/production.py hardened, validates hosts/origins/secret
    settings/test.py
    urls.py                admin + /api/v1/ mount, JSON 404/500 handlers
    api_v1.py              v1 route table
  apps/
    core/          health checks, shared abstract models, API exception handler
    accounts/      custom User model, roles, role-based permissions, JWT endpoints
    profiles/      matrimonial profiles, photos, preferences, privacy settings
    memberships/   plans and subscriptions
    payments/      orders, gateway transactions, invoices
    interactions/  interests, shortlists, profile views, blocks, reports
    notifications/ email / SMS / push / in-app notifications
    enquiries/     public enquiries and contact forms
    crm/           leads, telecaller assignment, call logs, follow-ups
    website_content/ CMS pages, banners, success stories, SEO metadata
    audit/         append-only audit trail of sensitive actions
```

`core`, `accounts`, `enquiries`, `profiles`, `interactions`, `memberships` and `notifications` contain
code today (the last four power the member dashboard, see section 4). The other apps are registered, migratable Django
apps whose `models.py` documents their responsibility; each gains models, serializers, views,
`urls.py` and tests when its module is implemented.

**Conventions for each app as it grows**

| File | Responsibility |
|------|----------------|
| `models.py` | Data and invariants only |
| `serializers.py` | Input validation and output shape; separate public vs owner vs staff serializers |
| `services.py` | Business operations that span models or apps (e.g. "accept interest") |
| `selectors.py` | Read queries that apply visibility/privacy rules |
| `views.py` | Thin: authenticate, authorise, call services/selectors, serialise |
| `permissions.py` | App-specific permission classes built on `accounts.permissions.HasRole` |
| `urls.py` | Mounted from `config/api_v1.py` |
| `tests/` | Split into a package once a single `tests.py` grows large |

Apps depend on `accounts` and `core`; avoid cycles between domain apps by going through services.

### Settings

`DJANGO_SETTINGS_MODULE` selects `config.settings.development`, `config.settings.production` or
`config.settings.test`. All settings read from environment variables (seeded from `backend/.env`
locally). Required values (`DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) have no
defaults; the process refuses to start without them and names the missing variable.

Production settings additionally refuse to start if:

- the secret key is shorter than 50 characters or a placeholder,
- `DJANGO_ALLOWED_HOSTS` is empty or contains `*`,
- any CORS/CSRF origin contains `*` or is not `https://`.

## 3. Frontend (`frontend/`)

Next.js 16 (App Router, React 19, TypeScript, Tailwind CSS 4, Cache Components enabled).

```
frontend/
  app/
    layout.tsx             root HTML shell, fonts, default metadata
    globals.css            design tokens (@theme) and base styles
    (public)/layout.tsx    header + footer for the public website
    (public)/page.tsx      home page
    (public)/status/       live API connectivity check (noindex)
    error.tsx, not-found.tsx, robots.ts, sitemap.ts
  components/
    layout/                site header (responsive nav) and footer
    ui/                    design-system primitives (Button, ButtonLink, Container)
  features/
    system-status/         feature module: API call + server component
  lib/
    config.ts              Zod-validated public configuration
    api/client.ts          centralised fetch client, ApiError
    site.ts                navigation definition
    utils.ts
  types/
    api.ts                 types shared with the API
```

**Planned route groups** (each with its own layout, added when built):

| Group | Audience | Notes |
|-------|----------|-------|
| `(public)` | Visitors, search engines | Server-rendered, SEO metadata, sitemap |
| `(member)` | Signed-in members | `/dashboard/...`, noindex |
| `(admin)` | Admin, verification staff, content managers | `/admin/...`, noindex |
| `(crm)` | Telecaller managers, telecallers | `/crm/...`, noindex |

Feature code lives in `features/<feature>/` (API calls, components, schemas, hooks) so pages stay
thin. Forms use React Hook Form with Zod schemas (both installed).

**Configuration.** `NEXT_PUBLIC_API_BASE_URL` is the public API base URL. Because `NEXT_PUBLIC_*`
values are inlined at build time, a new value requires a rebuild. Server-side code may use the
optional `API_INTERNAL_BASE_URL` (e.g. a private network address).

## 4. Authentication and authorisation

### Identity

- Custom user model `accounts.User`, created before the first migration.
- Login identifier: email (unique, stored lower-case) with a password. Phone number (E.164, unique,
  optional) stays on the account as contact and profile information.
- `public_id` (UUID) is the identifier exposed to clients and placed in tokens. The sequential
  primary key is never exposed.
- Passwords are hashed with Django's default PBKDF2 hasher; minimum length 10 plus Django's
  common/numeric/similarity validators.

### Roles

| Role (`User.role`) | Purpose |
|--------------------|---------|
| `member` | Matrimony member (default for new accounts) |
| `super_admin` | Full access; allowed by every role check |
| `admin` | Platform administration |
| `verification_staff` | Profile and document verification |
| `telecaller_manager` | Manages telecallers, assigns leads |
| `telecaller` | Works assigned leads |
| `content_manager` | Website content |

Roles are enforced in the API with DRF permission classes in `apps/accounts/permissions.py`
(`IsMember`, `IsAdministrator`, `IsVerificationStaff`, `IsTelecallerManager`, `IsTelecaller`,
`IsContentManager`). The default DRF permission is `IsAuthenticated`, so every endpoint is private
unless it explicitly opts in to public access. Object-level rules (e.g. "a telecaller may only see
leads assigned to them") are added per app as `has_object_permission` checks and queryset filters.

`is_staff` only controls access to the Django admin site; it is not used for API authorisation.
Members can never be `is_staff`/`is_superuser` (enforced in `User.clean`).

Fine-grained permissions inside a role (e.g. "can issue refunds") can be layered on with Django's
built-in `Group`/`Permission` models, which the custom user model supports via `PermissionsMixin`.

### Tokens (implemented)

`djangorestframework-simplejwt`:

- Access token: 15 minutes (configurable). Refresh token: 7 days (configurable).
- Refresh tokens rotate on every use; the previous one is blacklisted (`token_blacklist` app).
  Reusing an old refresh token fails.
- Logout = blacklist the refresh token.
- Token endpoints are rate-limited (`API_THROTTLE_AUTH`, default 10/min per client).

### Web browser strategy (implemented)

The browser never sees or stores tokens in JavaScript-accessible storage (no `localStorage`).

1. The login form posts to a Next.js server endpoint (Route Handler or Server Action).
2. That endpoint calls `POST /api/v1/auth/login/` server-to-server (email + password, members only).
3. It stores the access and refresh tokens in **HTTP-only, `Secure`, `SameSite=Lax`** cookies
   scoped to the website domain.
4. Server Components and Route Handlers read the cookie and call Django with
   `Authorization: Bearer <access>`. Expired access tokens are refreshed server-side by
   `frontend/proxy.ts` before `/dashboard/*` and `/profile/*` requests; `/dashboard/*` without a
   session redirects to `/login?next=…`.
5. Mutations go through Server Actions or Route Handlers, which verify the `Origin` header
   (built into Server Actions); `SameSite=Lax` blocks cross-site cookie sending.
6. Logout blacklists the refresh token and clears the cookies.
7. "Keep me signed in" (`mm_remember`, HTTP-only) makes the cookies last until the refresh token
   expires; without it they are browser-session cookies. `proxy.ts` keeps the choice when it
   renews tokens. Signing in again blacklists any refresh token the browser still held.

This keeps one token-based auth model for all clients while giving browsers cookie-level
protection against token theft by XSS. Django `SessionAuthentication` (with CSRF) remains enabled
for the Django admin and the browsable API.

### Mobile strategy

Mobile apps call `/api/v1/auth/token/` directly and send `Authorization: Bearer <access>`.
Tokens are stored in the platform secure store (iOS Keychain, Android Keystore/EncryptedSharedPreferences),
never in plain preferences or files. Refresh rotation and blacklisting apply identically.

### Email and password sign-in (implemented for members)

- `apps/accounts/password_auth.py`: `POST /auth/login/`, `/auth/password/reset/` and
  `/auth/password/reset/confirm/` (docs/api-specification.md). Passwords go through
  `django.contrib.auth.authenticate` and `set_password` (PBKDF2, `AUTH_PASSWORD_VALIDATORS`); errors
  are generic, and requests for unknown addresses look the same as real ones.
- Per-address limits (failed logins, reset emails) are rows in `accounts_authattempt` keyed by an
  HMAC of the address, so they hold across API processes; per-IP limits are DRF scoped throttles.
- Members created before passwords existed (SMS login) have no usable password. They set one with
  "Forgot password?": the emailed link proves they control the account's address and also sets
  `email_verified_at`. No password is ever generated for them.
- `apps/notifications/mail.py` sends via `EMAIL_PROVIDER`: `smtp`, or `console` (development: emails,
  including reset links, are printed by the API server) / `locmem` (tests). Production refuses the
  last two; unset means password reset answers `503` and the website says so.
- Website pages: `/login`, `/forgot-password`, `/reset-password` (`features/auth/`). The reset page
  reads the token from the URL fragment, then removes it from the address bar.
- Run `python manage.py purge_auth_attempts` daily to delete old attempt records.

### SMS OTP login (API only)

The website no longer offers SMS login; these endpoints remain for API clients and can be turned
off by leaving `SMS_PROVIDER` empty (they then answer `503`).

- `apps/accounts/otp.py` issues and checks codes; `PhoneOTPChallenge` stores only an HMAC of each
  code (keyed with `SECRET_KEY`, bound to the challenge, purpose and number). Codes come from
  `secrets`, expire after `OTP_TTL_SECONDS`, are single-use, allow `OTP_MAX_VERIFY_ATTEMPTS`
  wrong guesses, and a new code invalidates older ones.
- Per-number cooldown and hourly cap are counted in MySQL, so they hold across API processes;
  per-IP limits use DRF scoped throttles (local-memory cache: per process until Redis is added).
- Unregistered numbers get the same `202` and a challenge that can never verify, so the endpoint
  doesn't reveal who is registered. Staff accounts can't use phone login.
- `apps/notifications/sms.py` sends via `SMS_PROVIDER`: `msg91` (DLT template), or `console`
  (development, codes in the server log) / `locmem` (tests). Production refuses the last two;
  unset means SMS login answers `503`.
- Run `python manage.py purge_otp_challenges` daily to delete old challenges.

### Member dashboard (implemented)

- **Frontend:** `app/(dashboard)/dashboard/*` with its own shell (sidebar on large screens, bottom
  bar and drawer on phones). Pages are Server Components that read data through
  `features/dashboard/server-api.ts`; every change goes through `features/dashboard/actions.ts`
  (Server Actions) and the page re-renders from the API's answer. Photo uploads use the Route Handler
  `app/(dashboard)/dashboard/photos/upload/route.ts` so the browser can show progress.
- **Backend:** `profiles` (Profile, PartnerPreference, ProfilePhoto), `interactions` (Interest,
  Shortlist), `memberships` (Subscription; plan ids match `frontend/features/packages/packages.ts`),
  `notifications` (in-app Notification). Rules live in each app's `services.py`; interest changes
  lock the row in a transaction. Endpoints are listed in [api-specification.md](api-specification.md).
- **Review:** new profiles are `draft` until the member submits them, then staff approve or request
  changes in the Django admin; only `active`, visible profiles are shown to other members. Photos are
  `pending` until approved. Name, gender and date of birth are fixed once a profile is submitted.
- **Photos:** decoded with Pillow, re-encoded as JPEG (metadata dropped) under random names in
  `MEDIA_ROOT`, and served only through signed URLs that expire. In production, keep `MEDIA_ROOT`
  on persistent storage (or switch to private object storage) and never expose it as a static path.
- **Memberships:** staff record a subscription after an offline payment and activate it in the admin;
  there is no online payment, and nothing in the browser can activate a plan.

## 5. Security baseline

- `DEBUG` is forced off in production settings.
- HTTPS redirect, HSTS (1 year), secure session/CSRF cookies in production.
  HSTS preload is opt-in (`DJANGO_SECURE_HSTS_PRELOAD`) because it is hard to undo.
- CORS: explicit origin list only, credentials allowed, restricted to `/api/*`.
- `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`.
- API renders JSON only in production (browsable API in development).
- Unhandled API exceptions are logged server-side and return a generic JSON 500.
- Health endpoints return only status/service/version, never configuration or error details.
- Uploaded media is stored outside any public path; future access goes through permission-checked
  views (or signed URLs from object storage).
- Private profile data (contact details, documents, photos marked private) will be exposed only
  through owner/staff serializers and must be audit-logged when accessed by staff.

## 6. API documentation

`drf-spectacular` generates an OpenAPI 3 schema from the code:

- `GET /api/v1/schema/` — OpenAPI schema (YAML; `?format=json` for JSON)
- `GET /api/v1/docs/` — Swagger UI

Enabled by default in development, disabled by default in production (`API_DOCS_ENABLED`).
Human-written conventions are in [api-specification.md](api-specification.md).

## 7. Deployment outline (future)

- Backend: `gunicorn config.wsgi` behind a TLS-terminating reverse proxy (nginx or a load
  balancer), `DJANGO_SETTINGS_MODULE=config.settings.production`, `collectstatic`, migrations run
  as a release step.
- Frontend: `next build && next start` (or a managed Node host), built with production
  `NEXT_PUBLIC_*` values.
- MySQL 8.x managed instance with automated backups; app user without global privileges.
- Shared cache (Redis) for throttling and caching once more than one API process runs; the default
  local-memory cache is per-process.
- Object storage for media; error reporting service for both apps.
