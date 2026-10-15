"""
Settings for automated tests.

Tests run against MySQL by default (Django creates and destroys a separate
test_<DB_NAME> database; the user in DB_USER needs CREATE/DROP privileges).

Set TEST_DATABASE=sqlite to run the suite against a throwaway in-memory
SQLite database when no MySQL server is available, e.g. a quick local check.
This never affects the development or production database.
"""
import logging

from django.core.management.utils import get_random_secret_key

from config.env import env

# Tests should not require a real secret; generate one per run if unset.
env.ENVIRON.setdefault("DJANGO_SECRET_KEY", get_random_secret_key())

from config.env import mysql_database_config  # noqa: E402

from .base import *  # noqa: E402,F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
API_DOCS_ENABLED = True

if env.str("TEST_DATABASE", default="mysql").lower() == "sqlite":
    logging.getLogger(__name__).warning(
        "TEST_DATABASE=sqlite: running tests on in-memory SQLite, not MySQL."
    )
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
else:
    DATABASES = {"default": mysql_database_config()}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Throttling would make repeated test requests flaky.
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
