"""
Environment variable loading and validation.

Values are read from the process environment, optionally seeded from
backend/.env (never committed). Missing or invalid required values raise
ImproperlyConfigured at startup instead of failing later at runtime.
"""
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

# Real environment variables always take precedence over the .env file.
# Set DJANGO_READ_ENV_FILE=False to ignore the file (e.g. in containers).
_env_file = BASE_DIR / ".env"
if env.bool("DJANGO_READ_ENV_FILE", default=True) and _env_file.is_file():
    environ.Env.read_env(str(_env_file), overwrite=False)


def require(name: str) -> str:
    """Return a required, non-empty string variable or fail with a clear message."""
    value = env.str(name, default="").strip()
    if not value:
        raise ImproperlyConfigured(
            f"Environment variable {name} is required. "
            "Copy backend/.env.example to backend/.env and set it."
        )
    return value


def mysql_database_config() -> dict:
    """Build the MySQL DATABASES['default'] entry from DB_* variables."""
    port = env.str("DB_PORT", default="3306")
    if not port.isdigit():
        raise ImproperlyConfigured("DB_PORT must be a number.")

    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": require("DB_NAME"),
        "USER": require("DB_USER"),
        "PASSWORD": require("DB_PASSWORD"),
        "HOST": env.str("DB_HOST", default="127.0.0.1"),
        "PORT": port,
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "isolation_level": "read committed",
        },
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }
