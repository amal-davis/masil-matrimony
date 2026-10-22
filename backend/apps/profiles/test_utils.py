"""Shared helpers for the dashboard test suites (profiles, interactions, memberships, notifications)."""
import io
import itertools
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.roles import Role

from . import services
from .choices import ProfileStatus

User = get_user_model()
PASSWORD = "Str0ng-test-passphrase"
_counter = itertools.count(1)


def make_user(role=Role.MEMBER, **fields):
    n = next(_counter)
    return User.objects.create_user(
        email=f"user{n}@example.com",
        password=PASSWORD,
        phone_number=f"+9198{n:08d}",
        role=role,
        **fields,
    )


def birth_date(age: int) -> date:
    # 1 January: the birthday has always passed, so the age is exact.
    return date(date.today().year - age, 1, 1)


COMPLETE_FIELDS = {
    "height_cm": 170,
    "marital_status": "never_married",
    "religion": "hindu",
    "community": "nair",
    "mother_tongue": "malayalam",
    "state": "Kerala",
    "district": "Thrissur",
    "highest_education": "B.Tech",
    "occupation": "Engineer",
    "about": "A short introduction.",
}


def make_profile(user=None, gender="male", age=None, status=ProfileStatus.ACTIVE, complete=True, **fields):
    user = user or make_user()
    age = age or (28 if gender == "male" else 25)
    values = {
        "created_for": "self",
        "display_name": fields.pop("display_name", "Test"),
        "gender": gender,
        "date_of_birth": birth_date(age),
        **(COMPLETE_FIELDS if complete else {}),
        **fields,
    }
    profile = services.create_profile(user, **values)
    if status != ProfileStatus.DRAFT:
        profile.status = status
        profile.save()
    return profile


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def image_bytes(fmt="JPEG", size=(400, 500), color=(180, 40, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def upload(data=None, name="my-holiday.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data if data is not None else image_bytes(), content_type=content_type)


class TempMediaMixin:
    """Store uploaded files in a throwaway directory for the test case."""

    @classmethod
    def setUpClass(cls):
        cls._media_dir = tempfile.mkdtemp(prefix="mm-test-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
