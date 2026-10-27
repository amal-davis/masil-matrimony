"""
Shared Django settings. Environment-specific modules import from here.

DATABASES is intentionally not defined here: each environment module sets it
explicitly so that MySQL is always a deliberate choice.
"""
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured

from config.env import BASE_DIR, env, require

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = require("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    # Django Unfold styles the admin; it must come before django.contrib.admin.
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.profiles",
    "apps.memberships",
    "apps.payments",
    "apps.interactions",
    "apps.matchmaking",
    "apps.notifications",
    "apps.enquiries",
    "apps.crm",
    "apps.website_content",
    "apps.audit",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level overrides, e.g. the admin dashboard (templates/admin/index.html).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Path of the Django admin site. Use a non-default value in production.
ADMIN_URL = env.str("DJANGO_ADMIN_URL", default="admin/")

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env.str("DJANGO_TIME_ZONE", default="Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static and media files
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Brand assets used by the admin (static/brand/).
STATICFILES_DIRS = [BASE_DIR / "static"]

# Uploaded files (profile photos, documents). Never served publicly by
# default: access will go through permission-checked views.
MEDIA_URL = "media/"
MEDIA_ROOT = env.path("DJANGO_MEDIA_ROOT", default=BASE_DIR / "media")

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Deny by default: every endpoint must opt in to public access.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env.str("API_THROTTLE_ANON", default="60/min"),
        "user": env.str("API_THROTTLE_USER", default="300/min"),
        "auth": env.str("API_THROTTLE_AUTH", default="10/min"),
        # Public contact form, per IP address.
        "enquiries": env.str("API_THROTTLE_ENQUIRIES", default="5/hour"),
        # SMS codes, per IP address. Per-number limits are enforced separately (OTP_* below).
        # Sign-in code requests; registration starts and resends; code checks (both).
        "otp_request": env.str("API_THROTTLE_OTP_REQUEST", default="10/hour"),
        "register": env.str("API_THROTTLE_REGISTER", default="10/hour"),
        "otp_verify": env.str("API_THROTTLE_OTP_VERIFY", default="20/hour"),
        # Per member.
        "photo_upload": env.str("API_THROTTLE_PHOTO_UPLOAD", default="30/hour"),
        "interest_send": env.str("API_THROTTLE_INTEREST_SEND", default="100/day"),
        "contact_view": env.str("API_THROTTLE_CONTACT_VIEW", default="60/hour"),
        "message_send": env.str("API_THROTTLE_MESSAGE_SEND", default="120/hour"),
        # Membership checkout (order creation, verification, status checks), per member.
        "payments": env.str("API_THROTTLE_PAYMENTS", default="30/hour"),
        # A member changing their own email address, per member.
        "email_update": env.str("API_THROTTLE_EMAIL_UPDATE", default="10/hour"),
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "public_id",
    "USER_ID_CLAIM": "user_id",
    # Active, and mobile-verified if a member: checked at sign-in and on every refresh,
    # so a session can't outlive a suspension or start before verification.
    "USER_AUTHENTICATION_RULE": "apps.accounts.permissions.user_authentication_rule",
}

# --------------------------------------------------------------------------
# SMS one-time codes (apps/accounts/otp.py, apps/notifications/sms.py)
# --------------------------------------------------------------------------
OTP_CODE_LENGTH = env.int("OTP_CODE_LENGTH", default=6)
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)
# Codes per mobile number (sign-in and registration together) per hour and per day.
OTP_MAX_REQUESTS_PER_HOUR = env.int("OTP_MAX_REQUESTS_PER_HOUR", default=5)
OTP_MAX_REQUESTS_PER_DAY = env.int("OTP_MAX_REQUESTS_PER_DAY", default=10)
# Wrong guesses allowed per code.
OTP_MAX_VERIFY_ATTEMPTS = env.int("OTP_MAX_VERIFY_ATTEMPTS", default=5)
# How long after its last code a registration can still be resent (to the same or a
# corrected number) without filling in the form again.
OTP_REGISTRATION_WINDOW_SECONDS = env.int("OTP_REGISTRATION_WINDOW_SECONDS", default=3600)

if not 4 <= OTP_CODE_LENGTH <= 10:
    raise ImproperlyConfigured("OTP_CODE_LENGTH must be between 4 and 10.")
if OTP_TTL_SECONDS < 60 or OTP_RESEND_COOLDOWN_SECONDS < 1 or OTP_MAX_VERIFY_ATTEMPTS < 1:
    raise ImproperlyConfigured("OTP_TTL_SECONDS (>= 60), OTP_RESEND_COOLDOWN_SECONDS and OTP_MAX_VERIFY_ATTEMPTS must be positive.")

# Country calling codes (digits, no "+") whose mobile numbers may register and sign in
# (apps/accounts/phone.py). Only list countries the SMS provider can deliver to:
# India needs a DLT-approved template; others need MSG91's international route.
SMS_ALLOWED_COUNTRY_CODES = [
    code.strip().lstrip("+") for code in env.list("SMS_ALLOWED_COUNTRY_CODES", default=["91"]) if code.strip()
]
if not SMS_ALLOWED_COUNTRY_CODES or not all(code.isdigit() and len(code) <= 3 for code in SMS_ALLOWED_COUNTRY_CODES):
    raise ImproperlyConfigured("SMS_ALLOWED_COUNTRY_CODES must list calling codes such as 91,971.")

# "" (not configured), "msg91", or the local-only "console" / "locmem".
SMS_PROVIDER = env.str("SMS_PROVIDER", default="").strip().lower()
SMS_TIMEOUT_SECONDS = env.int("SMS_TIMEOUT_SECONDS", default=10)
MSG91_AUTH_KEY = env.str("MSG91_AUTH_KEY", default="")
MSG91_OTP_TEMPLATE_ID = env.str("MSG91_OTP_TEMPLATE_ID", default="")
# Name of the variable that holds the code in the MSG91 template, e.g. ##otp## -> "otp".
MSG91_OTP_VARIABLE = env.str("MSG91_OTP_VARIABLE", default="otp")

# Public URL of the website, for links in emails (e.g. https://www.example.com).
FRONTEND_URL = env.str("FRONTEND_URL", default="").rstrip("/")

# --------------------------------------------------------------------------
# Membership payments (apps/payments): Razorpay Orders API + Standard Checkout
# --------------------------------------------------------------------------
# From the Razorpay Dashboard (Account & Settings > API Keys). Only the key id ever reaches
# the browser; the key secret and the webhook secret stay on this server.
RAZORPAY_KEY_ID = env.str("RAZORPAY_KEY_ID", default="").strip()
RAZORPAY_KEY_SECRET = env.str("RAZORPAY_KEY_SECRET", default="").strip()
# The secret entered when creating the webhook (Dashboard > Webhooks). Not the API key secret.
RAZORPAY_WEBHOOK_SECRET = env.str("RAZORPAY_WEBHOOK_SECRET", default="").strip()
# "test" (rzp_test_ keys, no real money) or "live" (rzp_live_ keys). Must match the key id.
RAZORPAY_MODE = env.str("RAZORPAY_MODE", default="test").strip().lower()
RAZORPAY_TIMEOUT_SECONDS = env.int("RAZORPAY_TIMEOUT_SECONDS", default=15)
if RAZORPAY_MODE not in ("test", "live"):
    raise ImproperlyConfigured("RAZORPAY_MODE must be 'test' or 'live'.")
if RAZORPAY_KEY_ID and not RAZORPAY_KEY_ID.startswith(f"rzp_{RAZORPAY_MODE}_"):
    raise ImproperlyConfigured(f"RAZORPAY_KEY_ID must be an rzp_{RAZORPAY_MODE}_ key when RAZORPAY_MODE={RAZORPAY_MODE}.")

# GST rate (percent) for packages priced "plus applicable GST" (Silver, Gold, Diamond,
# Platinum). Empty until the business confirms it: those packages can't be bought online
# until then. Packages whose published price states its own rate (Royal) don't use this.
MEMBERSHIP_GST_RATE_PERCENT = env.str("MEMBERSHIP_GST_RATE_PERCENT", default="").strip()

# Gold and Diamond benefits offered "subject to availability" (apps.memberships.entitlements).
# Priority visibility is a ranking rule (apps.profiles.priority): on unless switched off.
PRIORITY_VISIBILITY_ENABLED = env.bool("PRIORITY_VISIBILITY_ENABLED", default=True)
# Members may ask for a matchmaker (apps.memberships.assistance). Switch off while no staff
# member can take requests; members then see "currently unavailable" and can't ask.
MATCHMAKING_ASSISTANCE_AVAILABLE = env.bool("MATCHMAKING_ASSISTANCE_AVAILABLE", default=True)

# Automatic match recommendations (apps.matchmaking.engine).
# Off: recommendations are published automatically (staff can still dismiss or flag one).
# On: members see only recommendations staff approved.
MATCH_REVIEW_REQUIRED = env.bool("MATCH_REVIEW_REQUIRED", default=False)
# How many of a member's best eligible candidates are stored per run.
MATCH_RECOMMENDATION_LIMIT = env.int("MATCH_RECOMMENDATION_LIMIT", default=100)
# Regenerate a member's recommendations right after they change their partner preferences.
MATCH_REGENERATE_ON_CHANGE = env.bool("MATCH_REGENERATE_ON_CHANGE", default=True)

# Seller details printed on payment receipts. Never invent these: leave empty until the
# business confirms them. Live payments are refused while the name or address is missing.
BILLING_SELLER_NAME = env.str("BILLING_SELLER_NAME", default="").strip()
BILLING_SELLER_ADDRESS = env.str("BILLING_SELLER_ADDRESS", default="").strip()
BILLING_SELLER_GSTIN = env.str("BILLING_SELLER_GSTIN", default="").strip().upper()
BILLING_CONTACT_EMAIL = env.str("BILLING_CONTACT_EMAIL", default="").strip()
BILLING_CONTACT_PHONE = env.str("BILLING_CONTACT_PHONE", default="").strip()
# Receipt numbers: <prefix>/<financial year>/<sequence>, e.g. MM/2026-27/000001.
RECEIPT_NUMBER_PREFIX = env.str("RECEIPT_NUMBER_PREFIX", default="MM").strip()
# Failed receipt emails are retried (retry_receipt_emails command, or the admin) up to this many attempts.
RECEIPT_EMAIL_MAX_ATTEMPTS = env.int("RECEIPT_EMAIL_MAX_ATTEMPTS", default=5)

# --------------------------------------------------------------------------
# Outgoing email (apps/notifications/mail.py)
# --------------------------------------------------------------------------
# "" (not configured), "smtp", or the local-only "console" / "locmem".
EMAIL_PROVIDER = env.str("EMAIL_PROVIDER", default="").strip().lower()
EMAIL_BACKENDS = {
    "smtp": "django.core.mail.backends.smtp.EmailBackend",
    "console": "django.core.mail.backends.console.EmailBackend",
    "locmem": "django.core.mail.backends.locmem.EmailBackend",
}
# Unconfigured: a backend that delivers nothing.
EMAIL_BACKEND = EMAIL_BACKENDS.get(EMAIL_PROVIDER, "django.core.mail.backends.dummy.EmailBackend")
EMAIL_HOST = env.str("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT_SECONDS", default=10)
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="")
SERVER_EMAIL = DEFAULT_FROM_EMAIL or "root@localhost"
# Contact-form enquiries are emailed here (apps/enquiries/notifications.py). Empty means the
# address the site sends from (DEFAULT_FROM_EMAIL), so enquiries arrive in that same mailbox.
ENQUIRY_NOTIFICATION_EMAIL = env.str("ENQUIRY_NOTIFICATION_EMAIL", default="").strip()

# --------------------------------------------------------------------------
# Member photos (apps/profiles/photos.py)
# --------------------------------------------------------------------------
# Largest accepted upload and the number of photos (excluding rejected ones) per profile.
PROFILE_PHOTO_MAX_BYTES = env.int("PROFILE_PHOTO_MAX_BYTES", default=8 * 1024 * 1024)
PROFILE_MAX_PHOTOS = env.int("PROFILE_MAX_PHOTOS", default=10)
# How long a signed photo URL keeps working.
PHOTO_URL_TTL_SECONDS = env.int("PHOTO_URL_TTL_SECONDS", default=3600)
# Public base URL of this API (e.g. https://api.example.com) for building photo URLs
# when requests arrive through an internal address; empty = use the request's host.
API_PUBLIC_URL = env.str("API_PUBLIC_URL", default="")

SPECTACULAR_SETTINGS = {
    "TITLE": "Matrimony Platform API",
    "DESCRIPTION": "Central REST API for the website, member portal, admin, CRM and mobile apps.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
}

# Interactive API docs (Swagger UI) and the OpenAPI schema endpoint.
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=False)

# --------------------------------------------------------------------------
# Admin site (Django Unfold). Callbacks live in apps/core/admin_site.py.
# --------------------------------------------------------------------------
# Shown as a badge in the admin header: "Development", "Staging" or "Production".
ADMIN_ENVIRONMENT_NAME = env.str("ADMIN_ENVIRONMENT_NAME", default="Production")


_SITE = "apps.core.admin_site"

UNFOLD = {
    "SITE_TITLE": "Massil Matrimony Admin",
    "SITE_HEADER": "Massil Matrimony",
    "SITE_SUBHEADER": "Administration",
    "SITE_URL": f"{_SITE}.site_url",
    "SITE_ICON": f"{_SITE}.site_icon",
    "SITE_SYMBOL": "favorite",
    "SITE_FAVICONS": [
        {"rel": "icon", "sizes": "any", "type": "image/png", "href": f"{_SITE}.site_icon"},
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "ENVIRONMENT": f"{_SITE}.environment_callback",
    "DASHBOARD_CALLBACK": f"{_SITE}.dashboard_callback",
    # The website's wine palette (frontend/app/globals.css: wine-600 #4b0f1e, wine-800 #2a0810).
    "COLORS": {
        "primary": {
            "50": "#fbf3f5",
            "100": "#f6e4e8",
            "200": "#edc8d0",
            "300": "#dfa0ae",
            "400": "#c96f84",
            "500": "#ad4a62",
            "600": "#8c2c44",
            "700": "#6e1d32",
            "800": "#4b0f1e",
            "900": "#2a0810",
            "950": "#1f050b",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        # Built per request (badges, permissions): apps/core/admin_site.py.
        "navigation": f"{_SITE}.sidebar_navigation",
    },
}

# --------------------------------------------------------------------------
# CORS / CSRF
# --------------------------------------------------------------------------
# Exact origins only. Wildcards are rejected in production settings.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --------------------------------------------------------------------------
# Security headers (hardened further in production.py)
# --------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOG_LEVEL = env.str("DJANGO_LOG_LEVEL", default="INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
