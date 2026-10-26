import json
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from . import sms
from .models import NotificationKind
from .services import notify

PHONE = "+919876543210"


def fake_response(payload):
    response = mock.MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__.return_value = response
    return response


@override_settings(
    SMS_PROVIDER="msg91",
    MSG91_AUTH_KEY="test-key",
    MSG91_OTP_TEMPLATE_ID="tmpl-1",
    MSG91_OTP_VARIABLE="otp",
)
class Msg91Tests(SimpleTestCase):
    def test_sends_code_as_template_variable(self):
        with mock.patch("urllib.request.urlopen", return_value=fake_response({"type": "success"})) as urlopen:
            sms.send_otp_sms(PHONE, "123456")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://control.msg91.com/api/v5/flow")
        self.assertEqual(request.get_header("Authkey"), "test-key")
        body = json.loads(request.data)
        self.assertEqual(body["template_id"], "tmpl-1")
        self.assertEqual(body["recipients"], [{"mobiles": "919876543210", "otp": "123456"}])

    def test_rejection_raises(self):
        with mock.patch("urllib.request.urlopen", return_value=fake_response({"type": "error", "message": "bad"})):
            with self.assertRaises(sms.SMSError):
                sms.send_otp_sms(PHONE, "123456")

    def test_network_failure_raises(self):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            with self.assertRaises(sms.SMSError):
                sms.send_otp_sms(PHONE, "123456")

    def test_http_errors_report_status_and_reason_but_never_the_key_or_code(self):
        import io
        import urllib.error

        for status, payload in ((401, b'{"type":"error","message":"Authentication failure"}'), (500, b"<html>")):
            error = urllib.error.HTTPError(
                "https://control.msg91.com/api/v5/flow", status, "Error", {}, io.BytesIO(payload)
            )
            with self.subTest(status=status), mock.patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(sms.SMSError) as raised:
                    sms.send_otp_sms(PHONE, "123456")
                message = str(raised.exception)
                self.assertIn(f"HTTP {status}", message)
                self.assertNotIn("test-key", message)
                self.assertNotIn("123456", message)
                if status == 401:
                    self.assertIn("Authentication failure", message)

    def test_unexpected_reply_is_not_treated_as_accepted(self):
        for payload in ({}, [], {"type": "pending"}):
            with self.subTest(payload=payload), mock.patch("urllib.request.urlopen", return_value=fake_response(payload)):
                with self.assertRaises(sms.SMSError):
                    sms.send_otp_sms(PHONE, "123456")

    @override_settings(MSG91_AUTH_KEY="")
    def test_missing_credentials_is_not_configured(self):
        with self.assertRaises(sms.SMSNotConfigured):
            sms.send_otp_sms(PHONE, "123456")


class ProviderSelectionTests(SimpleTestCase):
    @override_settings(SMS_PROVIDER="")
    def test_unset_provider_refuses_to_send(self):
        self.assertFalse(sms.sms_configured())
        with self.assertRaises(sms.SMSNotConfigured):
            sms.send_otp_sms(PHONE, "123456")

    @override_settings(SMS_PROVIDER="carrier-pigeon")
    def test_unknown_provider_is_a_configuration_error(self):
        self.assertFalse(sms.sms_configured())
        with self.assertRaises(ImproperlyConfigured):
            sms.send_otp_sms(PHONE, "123456")

    def load_production_settings(self, **overrides):
        """Import production settings in a fresh interpreter; return (exit code, stderr)."""
        # The developer's own email/SMS settings (loaded from backend/.env into this process)
        # must not leak into the check.
        mine = ("EMAIL_", "DEFAULT_FROM_EMAIL", "FRONTEND_URL", "SUPPORT_EMAIL", "SMS_", "MSG91_")
        env = {
            **{key: value for key, value in os.environ.items() if not key.startswith(mine)},
            "DJANGO_READ_ENV_FILE": "False",
            "DJANGO_SECRET_KEY": "x" * 60,
            "DJANGO_ALLOWED_HOSTS": "api.example.com",
            "CORS_ALLOWED_ORIGINS": "https://example.com",
            "CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DB_NAME": "db",
            "DB_USER": "user",
            "DB_PASSWORD": "pass",
            **overrides,
        }
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings.production"],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode, result.stderr

    def test_production_refuses_development_mocks(self):
        for provider in ["console", "locmem"]:
            with self.subTest(provider=provider):
                code, stderr = self.load_production_settings(SMS_PROVIDER=provider)
                self.assertNotEqual(code, 0)
                self.assertIn("development and tests only", stderr)

    def test_production_requires_msg91_credentials(self):
        code, stderr = self.load_production_settings(SMS_PROVIDER="msg91", MSG91_AUTH_KEY="", MSG91_OTP_TEMPLATE_ID="")
        self.assertNotEqual(code, 0)
        self.assertIn("MSG91_AUTH_KEY", stderr)

        code, _ = self.load_production_settings(SMS_PROVIDER="msg91", MSG91_AUTH_KEY="k", MSG91_OTP_TEMPLATE_ID="t")
        self.assertEqual(code, 0)

    @override_settings(SMS_PROVIDER="console")
    def test_console_never_logs_the_full_number(self):
        with self.assertLogs("apps.notifications.sms", level="INFO") as logs:
            sms.send_otp_sms(PHONE, "123456")
        self.assertNotIn(PHONE, "\n".join(logs.output))


class NotificationApiTests(TestCase):
    URL = "/api/v1/notifications/"

    def setUp(self):
        from apps.profiles.test_utils import client_for, make_user

        self.user = make_user()
        self.other = make_user()
        self.client = client_for(self.user)
        self.mine = [
            notify(self.user, NotificationKind.INTEREST_RECEIVED, f"Mine {i}", link="/dashboard") for i in range(3)
        ]
        self.theirs = notify(self.other, NotificationKind.INTEREST_RECEIVED, "Theirs")

    def test_list_is_scoped_to_recipient(self):
        body = self.client.get(self.URL).json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["unread_count"], 3)
        self.assertNotIn("Theirs", [item["title"] for item in body["results"]])
        self.assertEqual(set(body["results"][0]), {"id", "kind", "title", "body", "link", "created_at", "read"})

    def test_mark_read_and_unread_filter(self):
        target = self.mine[0]
        response = self.client.post(f"{self.URL}{target.public_id}/read/")
        self.assertEqual(response.status_code, 204)
        target.refresh_from_db()
        self.assertIsNotNone(target.read_at)
        # Marking again is harmless.
        self.assertEqual(self.client.post(f"{self.URL}{target.public_id}/read/").status_code, 204)

        unread = self.client.get(self.URL, {"unread": "1"}).json()
        self.assertEqual(unread["count"], 2)
        self.assertEqual(unread["unread_count"], 2)

    def test_cannot_mark_someone_elses(self):
        response = self.client.post(f"{self.URL}{self.theirs.public_id}/read/")
        self.assertEqual(response.status_code, 404)
        self.theirs.refresh_from_db()
        self.assertIsNone(self.theirs.read_at)

    def test_read_all(self):
        self.assertEqual(self.client.post(f"{self.URL}read-all/").status_code, 204)
        self.assertEqual(self.client.get(self.URL).json()["unread_count"], 0)
        self.theirs.refresh_from_db()
        self.assertIsNone(self.theirs.read_at)
