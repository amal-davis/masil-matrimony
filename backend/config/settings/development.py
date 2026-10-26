"""Local development settings. Uses the MySQL database configured in .env."""
from django.core.exceptions import ImproperlyConfigured

from config.env import env, mysql_database_config

from .base import *  # noqa: F401,F403

DEBUG = env.bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

DATABASES = {"default": mysql_database_config()}

API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=True)

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)

# Browsable API is convenient locally; production renders JSON only.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# Emails (including password-reset links) are printed to the server console until
# SMTP is configured. production.py refuses the console provider.
EMAIL_PROVIDER = env.str("EMAIL_PROVIDER", default="console").strip().lower()
EMAIL_BACKEND = EMAIL_BACKENDS.get(EMAIL_PROVIDER, EMAIL_BACKEND)  # noqa: F405
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="Massil Matrimony <noreply@localhost>")
FRONTEND_URL = env.str("FRONTEND_URL", default="http://localhost:3000").rstrip("/")

ADMIN_ENVIRONMENT_NAME = env.str("ADMIN_ENVIRONMENT_NAME", default="Development")

# Login codes are written to the server log until a real SMS provider is configured.
SMS_PROVIDER = env.str("SMS_PROVIDER", default="console").strip().lower()

# Real money only moves from production settings (production.py checks the live requirements).
if RAZORPAY_MODE == "live":  # noqa: F405
    raise ImproperlyConfigured("RAZORPAY_MODE=live is refused in development. Use rzp_test_ keys.")
