"""
Production settings. DEBUG is always off; HTTPS and secure cookies are enforced.
All hosts, origins and secrets must come from the environment.
"""
from django.core.exceptions import ImproperlyConfigured

from config.env import env, mysql_database_config

from .base import *  # noqa: F401,F403
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    DEFAULT_FROM_EMAIL,
    EMAIL_HOST,
    EMAIL_PROVIDER,
    FRONTEND_URL,
    MSG91_AUTH_KEY,
    MSG91_OTP_TEMPLATE_ID,
    BILLING_SELLER_ADDRESS,
    BILLING_SELLER_NAME,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    RAZORPAY_MODE,
    RAZORPAY_WEBHOOK_SECRET,
    SECRET_KEY,
    SMS_PROVIDER,
)

DEBUG = False

DATABASES = {"default": mysql_database_config()}

# --- Validation -----------------------------------------------------------
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("django-insecure", "change-me")):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a unique random value of at least 50 characters in production."
    )

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list explicit host names in production (no '*')."
    )

for _name, _origins in (
    ("CORS_ALLOWED_ORIGINS", CORS_ALLOWED_ORIGINS),
    ("CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS),
):
    for _origin in _origins:
        if "*" in _origin or not _origin.startswith("https://"):
            raise ImproperlyConfigured(
                f"{_name} entries must be explicit https:// origins in production; got {_origin!r}."
            )

# The development and test SMS mocks must never handle real login codes.
# An empty SMS_PROVIDER is allowed, but members can then neither register nor sign in:
# both answer 503 until a provider is configured.
if SMS_PROVIDER in ("console", "locmem"):
    raise ImproperlyConfigured(f"SMS_PROVIDER={SMS_PROVIDER!r} is for development and tests only.")
if SMS_PROVIDER == "msg91" and not (MSG91_AUTH_KEY and MSG91_OTP_TEMPLATE_ID):
    raise ImproperlyConfigured("SMS_PROVIDER=msg91 requires MSG91_AUTH_KEY and MSG91_OTP_TEMPLATE_ID.")

# Likewise for email. An empty EMAIL_PROVIDER is allowed: nothing is emailed.
if EMAIL_PROVIDER in ("console", "locmem"):
    raise ImproperlyConfigured(f"EMAIL_PROVIDER={EMAIL_PROVIDER!r} is for development and tests only.")
if EMAIL_PROVIDER == "smtp":
    if not (EMAIL_HOST and DEFAULT_FROM_EMAIL):
        raise ImproperlyConfigured("EMAIL_PROVIDER=smtp requires EMAIL_HOST and DEFAULT_FROM_EMAIL.")
    if not FRONTEND_URL.startswith("https://"):
        raise ImproperlyConfigured("FRONTEND_URL must be the site's https:// address for links in emails.")

# Live payments only with everything a paid customer is owed: webhook verification, a
# receipt that names the seller, and a working email to send it.
if RAZORPAY_MODE == "live":
    _missing = [
        name for name, value in (
            ("RAZORPAY_KEY_ID", RAZORPAY_KEY_ID),
            ("RAZORPAY_KEY_SECRET", RAZORPAY_KEY_SECRET),
            ("RAZORPAY_WEBHOOK_SECRET", RAZORPAY_WEBHOOK_SECRET),
            ("BILLING_SELLER_NAME", BILLING_SELLER_NAME),
            ("BILLING_SELLER_ADDRESS", BILLING_SELLER_ADDRESS),
        ) if not value
    ]
    if EMAIL_PROVIDER != "smtp":
        _missing.append("EMAIL_PROVIDER=smtp")
    if _missing:
        raise ImproperlyConfigured(f"RAZORPAY_MODE=live requires: {', '.join(_missing)}.")

# --- HTTPS ---------------------------------------------------------------
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)

# Only enable when the app sits behind a trusted proxy that sets this header.
if env.bool("DJANGO_TRUST_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Cookies -------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_DOMAIN = env.str("DJANGO_COOKIE_DOMAIN", default=None)
CSRF_COOKIE_DOMAIN = env.str("DJANGO_COOKIE_DOMAIN", default=None)
