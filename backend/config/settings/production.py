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
    MSG91_AUTH_KEY,
    MSG91_OTP_TEMPLATE_ID,
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
# An empty SMS_PROVIDER is allowed: SMS login then answers 503 until one is configured.
if SMS_PROVIDER in ("console", "locmem"):
    raise ImproperlyConfigured(f"SMS_PROVIDER={SMS_PROVIDER!r} is for development and tests only.")
if SMS_PROVIDER == "msg91" and not (MSG91_AUTH_KEY and MSG91_OTP_TEMPLATE_ID):
    raise ImproperlyConfigured("SMS_PROVIDER=msg91 requires MSG91_AUTH_KEY and MSG91_OTP_TEMPLATE_ID.")

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
