"""Local development settings. Uses the MySQL database configured in .env."""
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

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Login codes are written to the server log until a real SMS provider is configured.
SMS_PROVIDER = env.str("SMS_PROVIDER", default="console").strip().lower()
