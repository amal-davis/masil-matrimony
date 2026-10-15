# Database Design

## 1. Platform

- **MySQL 8.0.11+** (8.4 LTS recommended; Django 5.2 requires 8.0.11 or later), InnoDB.
- Character set **utf8mb4**, collation `utf8mb4_unicode_ci` (full Unicode, including Indic scripts and emoji).
- Connection options (see `backend/config/env.py`): `STRICT_TRANS_TABLES` SQL mode,
  `READ COMMITTED` isolation (Django's recommendation for MySQL), persistent connections
  (`DB_CONN_MAX_AGE`) with health checks.
- Time is stored in UTC (`USE_TZ = True`); displayed in `DJANGO_TIME_ZONE` (default `Asia/Kolkata`).
- Schema is managed **only** through Django migrations. Never alter tables by hand.

## 2. Conventions

| Topic | Convention |
|-------|-----------|
| Primary keys | `BIGINT` auto-increment (`BigAutoField`). Never exposed in the API. |
| External IDs | `public_id` `UUID` (unique) on any entity referenced by clients. |
| Timestamps | `created_at`, `updated_at` via `apps.core.models.TimeStampedModel`. |
| Table names | Django default `<app>_<model>` (e.g. `accounts_user`). |
| Choices | Stored as short strings (`TextChoices`), not integers, for readable data. |
| Money | `DECIMAL(12,2)` plus a currency code. Never floats. |
| Deletion | Members are deactivated (`is_active=False`) rather than hard-deleted so audit and payment history stay intact. Personal-data erasure requests are handled by anonymising fields. |
| Indexes | Index every foreign key (Django default) and the fields used by search filters and staff queues (status, role, dates). Add composite indexes deliberately when a query needs them. |
| Sensitive data | Contact details, ID documents and private photos are kept in separate fields/tables so they can be excluded from public serializers and audited on staff access. |

## 3. Current schema

Created by the initial migrations:

### `accounts_user` (custom user model)

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGINT PK | internal only |
| `public_id` | UUID (char(32)) | unique, exposed to clients and in JWTs |
| `email` | varchar(254) | unique, lower-cased; login identifier |
| `phone_number` | varchar(16) NULL | unique, E.164 format (e.g. `+919876543210`) |
| `password` | varchar(128) | Django password hash, never plaintext |
| `first_name`, `last_name` | varchar(150) | |
| `role` | varchar(32) | indexed; one of `member`, `super_admin`, `admin`, `verification_staff`, `telecaller_manager`, `telecaller`, `content_manager` |
| `is_active` | bool | deactivation instead of deletion |
| `is_staff` | bool | Django admin site access only |
| `is_superuser` | bool | |
| `email_verified_at`, `phone_verified_at` | datetime NULL | |
| `date_joined`, `last_login` | datetime | |

Plus `accounts_user_groups` and `accounts_user_user_permissions` (Django permissions).

### Framework tables

`django_migrations`, `django_content_type`, `auth_permission`, `auth_group`,
`auth_group_permissions`, `django_admin_log`, `django_session`,
`token_blacklist_outstandingtoken`, `token_blacklist_blacklistedtoken` (JWT refresh-token rotation).

## 4. Planned entities (by app)

These are the intended designs. They are **not yet implemented**; each will be refined when its
module is built.

### profiles
- **Profile** (1:1 User): profile_code (human-friendly, e.g. `MM100234`), created_for (self, son,
  daughter, sibling, relative), gender, date_of_birth, marital_status, height, religion, caste,
  sub_caste, mother_tongue, location (country/state/district/city), about, status
  (`draft`, `pending_verification`, `active`, `hidden`, `suspended`), verified_at, verified_by.
- **ProfileContact** (1:1 Profile): phone, alternate phone, email, address. Visible only to the
  owner, permitted members (per membership rules) and authorised staff; staff access is audited.
- **EducationCareer**, **FamilyDetails**, **Horoscope** (optional).
- **PartnerPreference** (1:1 Profile): age/height ranges, religions, castes, locations, education.
- **ProfilePhoto**: file reference, is_primary, visibility (`public`, `members`, `on_request`),
  moderation_status.
- **VerificationDocument**: document type, private file reference, status, reviewed_by, reviewed_at.
- **PrivacySettings**: who can view photos/contact details, profile visibility.

### memberships
- **MembershipPlan**: name, duration_days, price, currency, contact_view_limit, features (JSON), is_active.
- **Subscription**: user, plan, starts_at, ends_at, status, contact_views_used, payment.

### payments
- **PaymentOrder**: user, plan, amount, currency, status, gateway, gateway_order_id.
- **PaymentTransaction**: order, gateway_payment_id, status, raw_response (sanitised), verified signature flag.
- **Invoice**, **Refund**.

### interactions
- **Interest**: sender, receiver, status (`pending`, `accepted`, `declined`, `withdrawn`), message;
  unique per (sender, receiver).
- **Shortlist**, **ProfileView**, **Block**, **ProfileReport** (with moderation status).
- **ContactView**: records each paid contact reveal (counts against membership quota).

### notifications
- **Notification**: recipient, channel (`in_app`, `email`, `sms`, `push`), template, payload,
  status, sent_at, read_at.
- **NotificationPreference**, **DeviceToken** (mobile push).
- **OtpChallenge**: phone/email, hashed code, purpose, expires_at, attempts, consumed_at.

### enquiries
- **Enquiry**: name, phone, email, message, source, status, assigned_to (staff), converted_user.

### crm
- **Lead**: source (enquiry, registration, campaign, import), contact info, status pipeline,
  assigned_telecaller, next_follow_up_at.
- **CallLog**: lead, telecaller, started_at, duration, outcome, notes.
- **FollowUp**, **LeadAssignmentHistory**.

### website_content
- **Page** (slug, title, body, SEO title/description, published_at), **Banner**,
  **SuccessStory** (with consent flag), **FAQ**.

### audit
- **AuditLog** (append-only): actor, actor_role, action, target type/id, changes (JSON, without
  secrets), IP address, user agent, created_at. Indexed by actor, target and date. No update or
  delete permissions granted through the application.

## 5. Database users and privileges

| Account | Privileges | Used by |
|---------|-----------|---------|
| `matrimony_user` (example) | `ALL` on `matrimony_db.*` only | Django (runtime + migrations) |
| same user, test runs | `ALL` on `test_matrimony_db.*` | `manage.py test` creates/drops this database |
| `root` | Server administration | Humans only; never used by the app |

In production, consider a separate migration user with DDL rights and a runtime user limited to
`SELECT, INSERT, UPDATE, DELETE`.

## 6. Backups and safety

- Enable automated daily backups with point-in-time recovery in production.
- Take a backup before running migrations in production.
- Never run `flush`, `reset_db`, `DROP DATABASE` or `docker compose down -v` against a database
  that holds real data.
