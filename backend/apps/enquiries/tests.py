from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from .models import Enquiry
from .serializers import normalise_phone
from .views import EnquiryCreateView

VALID = {
    "name": "Anu Thomas",
    "email": "Anu.Thomas@Example.COM",
    "phone": "98765 43210",
    "message": "I would like to know more about registering a profile for my daughter.",
}


class EnquiryCreateTests(TestCase):
    url = "/api/v1/enquiries/"

    def setUp(self):
        self.client = APIClient()

    def post(self, data=None, **extra):
        return self.client.post(self.url, data if data is not None else VALID, format="json", **extra)

    def test_url_is_versioned(self):
        self.assertEqual(reverse("enquiries:create"), self.url)

    def test_valid_submission_is_stored(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        enquiry = Enquiry.objects.get()
        self.assertEqual(response.json(), {"id": str(enquiry.public_id)})
        self.assertEqual(enquiry.name, "Anu Thomas")
        self.assertEqual(enquiry.email, "Anu.Thomas@example.com")
        self.assertEqual(enquiry.phone, "+919876543210")
        self.assertEqual(enquiry.status, Enquiry.Status.NEW)
        self.assertEqual(enquiry.source, Enquiry.Source.CONTACT_FORM)

    def test_response_does_not_echo_personal_data(self):
        body = self.post().content.decode()
        for value in ("Anu", "98765", "Example", "daughter"):
            self.assertNotIn(value, body)

    def test_whitespace_is_trimmed(self):
        data = {**VALID, "name": "  Anu   Thomas ", "message": "   " + VALID["message"] + "  \n"}
        self.assertEqual(self.post(data).status_code, 201)
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.name, "Anu Thomas")
        self.assertEqual(enquiry.message, VALID["message"])

    def test_malayalam_name_is_accepted(self):
        self.assertEqual(self.post({**VALID, "name": "അനു തോമസ്"}).status_code, 201)

    def test_missing_fields_are_reported(self):
        response = self.post({})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"name", "email", "phone", "message"})
        self.assertFalse(Enquiry.objects.exists())

    def test_invalid_values_are_rejected(self):
        cases = {
            "name": ["A", "Anu123", "x" * 101, "<script>"],
            "email": ["not-an-email", "a@b", "x" * 250 + "@example.com"],
            "phone": ["12345", "+0123456789", "98765abcde", "+91 98765 43210 1234 5"],
            "message": ["too short", "x" * 2001, "          "],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value[:30]):
                    response = self.post({**VALID, field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.json())
        self.assertFalse(Enquiry.objects.exists())

    def test_honeypot_submissions_are_not_stored(self):
        response = self.post({**VALID, "website": "https://spam.example"})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(Enquiry.objects.exists())

    def test_oversized_request_is_rejected(self):
        response = self.post({**VALID, "padding": "x" * 20_000})
        self.assertEqual(response.status_code, 413)
        self.assertFalse(Enquiry.objects.exists())

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_no_authentication_or_csrf_token_needed(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(self.url, VALID, format="json")
        self.assertEqual(response.status_code, 201)

    def test_submissions_are_rate_limited(self):
        cache.clear()
        self.addCleanup(cache.clear)
        with mock.patch.object(EnquiryCreateView, "throttle_classes", [ScopedRateThrottle]), mock.patch.object(
            ScopedRateThrottle, "THROTTLE_RATES", {"enquiries": "2/hour"}
        ):
            statuses = [self.post().status_code for _ in range(3)]
        self.assertEqual(statuses, [201, 201, 429])
        self.assertEqual(Enquiry.objects.count(), 2)

    def test_message_is_not_logged(self):
        with self.assertLogs("apps.enquiries", level="INFO") as logs:
            self.post()
        output = "\n".join(logs.output)
        for value in ("Anu", "98765", "daughter", "example.com"):
            self.assertNotIn(value, output)

    def test_unexpected_error_does_not_leak_details(self):
        with mock.patch.object(
            Enquiry.objects, "create", side_effect=RuntimeError("db password=secret")
        ), self.assertLogs("apps.core.exceptions", level="ERROR"):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.content.decode())


class PhoneNormalisationTests(TestCase):
    def test_accepted_formats(self):
        cases = {
            "9876543210": "+919876543210",
            "+91 98765 43210": "+919876543210",
            "0091-98765-43210": "+919876543210",
            "098765 43210": "+919876543210",
            "0484 234 5678": "+914842345678",
            "+971 50 123 4567": "+971501234567",
            "+1 (415) 555-0123": "+14155550123",
            "+690 7290": "+6907290",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalise_phone(raw), expected)
