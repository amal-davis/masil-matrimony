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
| `email` | varchar(254) NULL | unique, lower-cased; staff login identifier; optional contact detail for members |
| `phone_number` | varchar(16) NULL | unique, E.164 format (e.g. `+919876543210`) |
| `password` | varchar(128) | Django password hash, never plaintext |
| `first_name`, `last_name` | varchar(150) | |
| `role` | varchar(32) | indexed; one of `member`, `super_admin`, `admin`, `verification_staff`, `telecaller_manager`, `telecaller`, `content_manager` |
| `is_active` | bool | deactivation instead of deletion |
| `is_staff` | bool | Django admin site access only |
| `is_superuser` | bool | |
| `phone_verified_at` | datetime NULL | set by a correct SMS code; required for members to sign in; cleared when the number changes |
| `email_verified_at`, `email_verification_sent_at` | datetime NULL | historical (email verification is no longer used) |
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
  Implemented as verification_status (`not_requested`, `requested`, `verified`, `declined`), verification_requested_at,
  verification_note, verified_at, verified_by: identity verification for the Verified badge, decided by staff only.
- **ProfileContact** (1:1 Profile): phone, alternate phone, email, address. Visible only to the
  owner, permitted members (per membership rules) and authorised staff; staff access is audited.
- **EducationCareer**, **FamilyDetails**, **Horoscope** (optional).
- **PartnerPreference** (1:1 Profile): age/height ranges, religions, castes, locations, education.
- **ProfilePhoto**: file reference, is_primary, visibility (`public`, `members`, `on_request`),
  moderation_status.
- **VerificationDocument**: document type, private file reference, status, reviewed_by, reviewed_at.
- **PrivacySettings**: who can view photos/contact details, profile visibility. Implemented so far as
  Profile fields: visibility, photo_visibility, contact_sharing (`hidden` by default / `paid_members`).

### memberships
- **MembershipPackage** (implemented): code (`free`, `silver`, `gold`, `diamond`, `platinum`, `royal`; fixed),
  category, display_order, is_available, website copy (name, subtitle, tagline, service label, description,
  benefits JSON, terms, CTA label), fee (decimal, excl. GST), fee_label, tax_treatment, stated_gst_rate,
  validity_months (null = Free, no expiry), contact_view_limit, outgoing_interest_limit (Free only).
  Fees, tax, validity and limits need the `change_package_terms` permission.
- **Subscription** (implemented): user, plan_code, status, starts_at, ends_at, and the terms copied from the
  package when recorded (package_fee, validity_months, contact_view_limit), contact_views_used. Planned: payment.
- **AssistanceRequest** (implemented): a Gold/Diamond member's matchmaking-assistance request: user, subscription
  (the membership that included it), status (`requested`, `assigned`, `in_progress`, `completed`,
  `unavailable`), member_note, assigned_to (staff user), assigned_at, closed_at, member_message (shown to the
  member), staff_note (internal). One open request per member (enforced in `apps/memberships/assistance.py`).
- **AssistanceEvent** (implemented): append-only history of an AssistanceRequest: status, assigned_to,
  changed_by, created_at.
- AssistanceRequest also has `kind`: `request` (Gold/Diamond) or `service` (the Platinum case, opened once per
  Platinum subscription when it is activated). Statuses also include `awaiting_member`, `follow_up`, `on_hold`,
  `cancelled` and `expired`. Permission `assign_assistancerequest` = see every case and assign matchmakers;
  other staff with `change_assistancerequest` see only cases assigned to them.
- **AssistanceNote** (implemented): case, author, body, visible_to_member (unticked = internal), created_at.
- **AssistanceFollowUp** (implemented): case, action, due_on, status (`scheduled`, `done`, `cancelled`),
  awaiting_member, outcome (internal), visible_to_member, created_by, completed_at.
- **AssistanceCandidate** (implemented): case, profile, added_by, staff_note (internal), shared_with_member,
  shared_at, member_response (`pending`, `interested`, `not_interested`); unique per (case, profile).
- **ContactExchange** (implemented): a Platinum case's proposed exchange of mobile numbers with one other
  member: case, other_profile, purpose, status (`pending`, `shared`, `declined`, `cancelled`),
  initiated_by, shared_at, closed_at, cancelled_by. Stores no numbers.
- Royal (also a `service` case, 12 months): AssistanceRequest adds service_plan and next_steps (staff, shown to
  the member) beside member_note (the member's own requirements, which they can update; member_note_updated_at),
  and Royal-only statuses `requirements`, `curation`, `awaiting_review`, `family`, `consult_requested`,
  `consult_scheduled` (the last two need a recorded request / member-confirmed consultation; `family` needs a
  permitted family contact).
- **Consultation** (implemented): Royal case, status (`requested`, `proposed`, `scheduled` only after the
  member confirms, `completed`, `cancelled`, `unavailable`), requested_by, member_note, address (restricted to
  the case's staff; never returned by member APIs), scheduled_for, confirmed_at, completed_at, member_message,
  outcome (internal). **ConsultationEvent**: append-only status and reschedule history.
- **FamilyContact** (implemented): Royal case, name, relationship, phone_number (case staff only; members see the
  last digits), purpose, permission (`pending`, `granted`, `withdrawn`; only the member grants or withdraws),
  statement (exact text agreed), granted_at, withdrawn_at, added_by. **FamilyCoordination**: an action recorded
  by staff while permission is granted: action, outcome (internal), visible_to_member, staff, created_at.
- **ContactConsent** (implemented): exchange, profile, statement (the exact text shown), decision (`pending`,
  `granted`, `declined`, `withdrawn`), decided_at, number_seen_at (the disclosure record); unique per
  (exchange, profile).

### matchmaking
- **MatchRecommendation** (implemented): one direction, "candidate suits member's partner preferences", from
  apps.profiles.matching: member, candidate (unique pair, never self), score (0-100), reasons, mismatched,
  not_stated, reverse_must_haves_met, algorithm_version, fingerprint (hash of the data evaluated), status
  (`active`, `stale`, `ineligible`), review_status (`not_required`, `pending`, `approved`, `flagged`,
  `dismissed`), reviewed_by, reviewed_at, review_note, hidden_by_member_at, first_generated_at,
  last_evaluated_at. Never deleted by regeneration. Proxy **PendingRecommendation** = the review queue.
- **MatchPair** (implemented): one per unordered pair (profile_low < profile_high), links low_to_high and
  high_to_low; mutual = both directions current; mutual_since. Proxy **MutualMatch**. Interests are read live,
  never stored here.
- **ReviewEvent** (implemented): append-only review history (staff null = re-queued after a data change).
- **MatchRun** (implemented): each generation run with its counts.

### payments
- **Purchase** (implemented): one Razorpay order for one package, with a snapshot of what was sold (package
  code and name, validity, contact limit, tax treatment, fee, GST rate and amount, total, paise, currency) and
  the billing contact; status (`awaiting_payment`, `authorized`, `paid`, `failed`, `needs_review`,
  `order_failed`), mode (test/live), razorpay_order_id, razorpay_payment_id, paid_at, subscription (set once, when
  paid), refund_status (`none`, `partial`, `full`), refunded_amount_subunits, refunded_at (as reported by
  Razorpay; refunds are made in Razorpay's dashboard). Permissions `view_purchase_financials` and
  `export_purchase`. There are no discounts.
- **RazorpayPayment** (implemented): each payment attempt Razorpay reports for an order, with
  amount_refunded_subunits.
- **PurchaseEvent** (implemented): append-only history of a purchase's payment and refund status, the source
  (order, checkout callback, webhook, member or staff status check) and the staff member for staff checks.
- **Receipt**, **ReceiptSequence**, **WebhookEvent** (implemented). No signatures, card data or secrets are stored.

### interactions
- **Interest**: sender, receiver, status (`pending`, `accepted`, `declined`, `withdrawn`), message;
  unique per (sender, receiver).
- **Shortlist** (implemented), **Block**, **ProfileReport** (with moderation status).
- **ProfileView** (implemented): viewer, profile, first_viewed_at, last_viewed_at, visits; one per (viewer,
  profile); a visit counts again only after 30 minutes.
- **Conversation** (implemented): member_a < member_b (one per pair), started_by, last_message_at.
  **Message**: conversation, sender, body (≤ 2000), created_at, read_at.
- **ContactView** (implemented): subscription, viewer, profile; one per (subscription, profile), so a limit
  counts different members per subscription. Interest.counts_toward_free_limit marks interests that count
  toward the Free package's limit.

### notifications
- **Notification**: recipient, channel (`in_app`, `email`, `sms`, `push`), template, payload,
  status, sent_at, read_at.
- **NotificationPreference**, **DeviceToken** (mobile push).
- **PhoneOTPChallenge** (implemented, `accounts`): public_id, purpose (`login`/`register`), phone_number, user (login), HMAC of the code, expires_at, failed_attempts, used_at, invalidated_at, registration (JSON details awaiting verification). **OTPNumberLock**: HMAC key per number, for serialising code requests.

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
