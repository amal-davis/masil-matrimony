import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from config.env import mysql_database_config

BACKEND_DIR = Path(__file__).resolve().parents[2]


class HealthEndpointTests(SimpleTestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "matrimony-api", "api_version": "v1"},
        )

    def test_health_url_is_versioned(self):
        self.assertEqual(reverse("health"), "/api/v1/health/")

    def test_health_does_not_leak_configuration(self):
        body = self.client.get("/api/v1/health/").content.decode()
        db = settings.DATABASES["default"]
        for secret in (settings.SECRET_KEY, db.get("PASSWORD"), db.get("USER")):
            if secret:
                self.assertNotIn(secret, body)

    def test_health_rejects_writes(self):
        response = self.client.post("/api/v1/health/")
        self.assertEqual(response.status_code, 405)


class ReadinessEndpointTests(TestCase):
    def test_ready_when_database_reachable(self):
        response = self.client.get("/api/v1/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_unavailable_when_database_down_without_leaking_error(self):
        with mock.patch(
            "apps.core.views.connection.cursor",
            side_effect=DatabaseError("Access denied for user 'secret_user'"),
        ), self.assertLogs("apps.core.views", level="ERROR"):
            response = self.client.get("/api/v1/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertNotIn("secret_user", response.content.decode())


class ApiErrorHandlingTests(SimpleTestCase):
    def test_unknown_api_route_returns_json_404(self):
        response = self.client.get("/api/v1/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_api_docs_schema_available_when_enabled(self):
        response = self.client.get("/api/v1/schema/")
        self.assertEqual(response.status_code, 200)


class DatabaseConfigurationTests(SimpleTestCase):
    base_env = {
        "DB_NAME": "matrimony_db",
        "DB_USER": "matrimony_user",
        "DB_PASSWORD": "pw",
        "DB_HOST": "db.internal",
        "DB_PORT": "3307",
    }

    def test_builds_mysql_config_from_environment(self):
        with mock.patch.dict(os.environ, self.base_env):
            config = mysql_database_config()
        self.assertEqual(config["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(config["NAME"], "matrimony_db")
        self.assertEqual(config["HOST"], "db.internal")
        self.assertEqual(config["PORT"], "3307")
        self.assertEqual(config["OPTIONS"]["charset"], "utf8mb4")

    def test_missing_required_variable_fails_clearly(self):
        env = {**self.base_env, "DB_PASSWORD": ""}
        with mock.patch.dict(os.environ, env):
            with self.assertRaisesMessage(ImproperlyConfigured, "DB_PASSWORD"):
                mysql_database_config()

    def test_non_numeric_port_rejected(self):
        with mock.patch.dict(os.environ, {**self.base_env, "DB_PORT": "abc"}):
            with self.assertRaises(ImproperlyConfigured):
                mysql_database_config()


class ProductionSettingsTests(SimpleTestCase):
    """Load production settings in a clean subprocess with controlled env vars."""

    valid_env = {
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_SECRET_KEY": "x" * 30 + "-prod-test-only-not-a-real-key-0123456789",
        "DJANGO_ALLOWED_HOSTS": "api.example.com",
        "CORS_ALLOWED_ORIGINS": "https://www.example.com",
        "CSRF_TRUSTED_ORIGINS": "https://www.example.com",
        "DB_NAME": "n",
        "DB_USER": "u",
        "DB_PASSWORD": "p",
    }

    def load(self, **overrides):
        env = {
            key: value
            for key, value in os.environ.items()
            # Isolate from the developer's own configuration.
            if not key.startswith(("DJANGO_", "DB_", "CORS_", "CSRF_", "API_"))
        }
        env.update(self.valid_env)
        env.update(overrides)
        code = (
            "import django; from django.conf import settings; django.setup(); "
            "print(settings.DEBUG, settings.SESSION_COOKIE_SECURE, "
            "settings.CSRF_COOKIE_SECURE, settings.SECURE_SSL_REDIRECT)"
        )
        # Ignore backend/.env so only the variables passed here apply.
        env["DJANGO_READ_ENV_FILE"] = "False"
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_valid_production_settings_are_hardened(self):
        result = self.load()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["False", "True", "True", "True"])

    def test_rejects_short_secret_key(self):
        result = self.load(DJANGO_SECRET_KEY="too-short")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_rejects_wildcard_hosts(self):
        result = self.load(DJANGO_ALLOWED_HOSTS="*")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_rejects_wildcard_or_plain_http_cors(self):
        for origin in ("*", "http://www.example.com"):
            with self.subTest(origin=origin):
                result = self.load(CORS_ALLOWED_ORIGINS=origin)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("CORS_ALLOWED_ORIGINS", result.stderr)
