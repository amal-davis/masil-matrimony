import json
import uuid
from datetime import date

from django.test import TestCase, override_settings
from PIL import Image

from apps.accounts.roles import Role
from apps.interactions.models import Interest, InterestStatus

from .choices import PhotoStatus, PhotoVisibility, ProfileStatus, Visibility
from .models import Profile, ProfilePhoto
from .test_utils import (
    TempMediaMixin,
    birth_date,
    client_for,
    image_bytes,
    make_profile,
    make_user,
    upload,
)

ME = "/api/v1/profiles/me/"
PHOTOS = "/api/v1/profiles/me/photos/"
MATCHES = "/api/v1/profiles/matches/"


def detail_url(code):
    return f"/api/v1/profiles/{code}/"


PRIVATE_ENDPOINTS = [
    ("get", "/api/v1/dashboard/summary/"),
    ("get", ME),
    ("post", ME),
    ("patch", ME),
    ("patch", "/api/v1/profiles/me/partner-preference/"),
    ("post", "/api/v1/profiles/me/submit/"),
    ("get", PHOTOS),
    ("post", PHOTOS),
    ("delete", f"/api/v1/profiles/me/photos/{uuid.uuid4()}/"),
    ("post", f"/api/v1/profiles/me/photos/{uuid.uuid4()}/primary/"),
    ("get", MATCHES),
    ("get", detail_url("MM123456")),
    ("post", "/api/v1/interests/"),
    ("get", "/api/v1/interests/received/"),
    ("get", "/api/v1/interests/sent/"),
    ("post", f"/api/v1/interests/{uuid.uuid4()}/accept/"),
    ("post", f"/api/v1/interests/{uuid.uuid4()}/decline/"),
    ("post", f"/api/v1/interests/{uuid.uuid4()}/withdraw/"),
    ("get", "/api/v1/shortlist/"),
    ("post", "/api/v1/shortlist/"),
    ("delete", "/api/v1/shortlist/MM123456/"),
    ("get", "/api/v1/memberships/me/"),
    ("get", "/api/v1/notifications/"),
    ("post", "/api/v1/notifications/read-all/"),
    ("post", f"/api/v1/notifications/{uuid.uuid4()}/read/"),
]


class AccessControlTests(TestCase):
    def test_private_endpoints_require_authentication(self):
        client = client_for()
        for method, url in PRIVATE_ENDPOINTS:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(client, method)(url, {}, format="json").status_code, 401)

    def test_staff_accounts_are_not_members(self):
        client = client_for(make_user(role=Role.ADMIN))
        for method, url in PRIVATE_ENDPOINTS:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(client, method)(url, {}, format="json").status_code, 403)


class CreateProfileTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = client_for(self.user)

    def payload(self, **overrides):
        return {
            "created_for": "self",
            "display_name": "Anjali",
            "gender": "female",
            "date_of_birth": str(birth_date(25)),
            **overrides,
        }

    def test_no_profile_yet(self):
        response = self.client.get(ME)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "no_profile")

    def test_create_profile(self):
        response = self.client.post(ME, self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertRegex(body["profile_code"], r"^MM\d{6}$")
        self.assertEqual(body["status"], ProfileStatus.DRAFT)
        self.assertFalse(body["identity_locked"])
        self.assertEqual(self.client.get(ME).json()["display_name"], "Anjali")

    def test_identity_fields_are_required(self):
        for field in ["created_for", "display_name", "gender", "date_of_birth"]:
            with self.subTest(field=field):
                data = self.payload()
                del data[field]
                response = self.client.post(ME, data, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertFalse(Profile.objects.exists())

    def test_minimum_age_by_gender(self):
        self.assertEqual(
            self.client.post(ME, self.payload(gender="female", date_of_birth=str(birth_date(17))), format="json").status_code,
            400,
        )
        response = self.client.post(ME, self.payload(gender="male", date_of_birth=str(birth_date(20))), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("21", response.json()["date_of_birth"][0])
        self.assertEqual(
            self.client.post(ME, self.payload(gender="male", date_of_birth=str(birth_date(21))), format="json").status_code,
            201,
        )

    def test_community_must_match_religion(self):
        response = self.client.post(ME, self.payload(religion="christian", community="nair"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("community", response.json())
        ok = self.client.post(ME, self.payload(religion="christian", community="marthoma"), format="json")
        self.assertEqual(ok.status_code, 201)

    def test_name_pattern(self):
        for name in ["A", "Anj@li", "R2D2", "<script>"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.post(ME, self.payload(display_name=name), format="json").status_code, 400)
        self.assertEqual(self.client.post(ME, self.payload(display_name="Mary-Ann O'Neil"), format="json").status_code, 201)

    def test_tag_list_limits(self):
        too_many = self.client.post(ME, self.payload(hobbies=[f"Hobby {i}" for i in range(11)]), format="json")
        self.assertEqual(too_many.status_code, 400)
        too_long = self.client.post(ME, self.payload(hobbies=["x" * 41]), format="json")
        self.assertEqual(too_long.status_code, 400)
        not_text = self.client.post(ME, self.payload(hobbies=[3]), format="json")
        self.assertEqual(not_text.status_code, 400)
        ok = self.client.post(ME, self.payload(hobbies=["  Reading ", "reading", "Music"]), format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["hobbies"], ["Reading", "Music"])

    def test_duplicate_create(self):
        self.client.post(ME, self.payload(), format="json")
        response = self.client.post(ME, self.payload(), format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Profile.objects.count(), 1)


class UpdateProfileTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.profile = make_profile(self.user, status=ProfileStatus.DRAFT, complete=False, display_name="Arjun")
        self.client = client_for(self.user)

    def test_partial_update_preserves_other_fields(self):
        self.client.patch(ME, {"occupation": "Teacher", "about": "Hello"}, format="json")
        response = self.client.patch(ME, {"height_cm": 172}, format="json")
        self.assertEqual(response.status_code, 200)
        body = self.client.get(ME).json()
        self.assertEqual(body["occupation"], "Teacher")
        self.assertEqual(body["about"], "Hello")
        self.assertEqual(body["height_cm"], 172)
        self.assertEqual(body["display_name"], "Arjun")

    def test_invalid_values_rejected(self):
        for data in [{"height_cm": 50}, {"marital_status": "complicated"}, {"visibility": "public"}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.patch(ME, data, format="json").status_code, 400)

    def test_cannot_change_read_only_fields(self):
        self.client.patch(ME, {"status": ProfileStatus.ACTIVE, "profile_code": "MM000001"}, format="json")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, ProfileStatus.DRAFT)
        self.assertNotEqual(self.profile.profile_code, "MM000001")

    def test_completion_and_submission(self):
        first = self.client.get(ME).json()
        self.assertLess(first["completion"]["percent"], 50)
        self.assertIn("Height", first["missing_for_review"])

        incomplete = self.client.post("/api/v1/profiles/me/submit/")
        self.assertEqual(incomplete.status_code, 409)
        self.assertEqual(incomplete.json()["code"], "incomplete")

        from .test_utils import COMPLETE_FIELDS

        self.client.patch(ME, COMPLETE_FIELDS, format="json")
        filled = self.client.get(ME).json()
        self.assertGreater(filled["completion"]["percent"], first["completion"]["percent"])
        self.assertEqual(filled["missing_for_review"], [])
        self.assertNotIn("Height", filled["completion"]["missing"])

        submitted = self.client.post("/api/v1/profiles/me/submit/")
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], ProfileStatus.PENDING_REVIEW)

        again = self.client.post("/api/v1/profiles/me/submit/")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["code"], "already_submitted")

    def test_identity_locked_after_submit(self):
        self.profile.status = ProfileStatus.PENDING_REVIEW
        self.profile.save()
        for data in [{"display_name": "Someone"}, {"gender": "female"}, {"date_of_birth": str(birth_date(30))}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.patch(ME, data, format="json").status_code, 400)
        # Sending the unchanged value is fine, and other fields stay editable.
        ok = self.client.patch(ME, {"display_name": "Arjun", "about": "Updated"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.display_name, "Arjun")

    def test_partner_preference(self):
        url = "/api/v1/profiles/me/partner-preference/"
        self.assertEqual(self.client.patch(url, {"age_min": 30, "age_max": 25}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"religions": ["martian"]}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"communities": ["unknown"]}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"age_min": 10}, format="json").status_code, 400)

        ok = self.client.patch(url, {"age_min": 23, "age_max": 29, "religions": ["hindu"]}, format="json")
        self.assertEqual(ok.status_code, 200)
        # Partial: only the max changes, and it's checked against the stored min.
        self.assertEqual(self.client.patch(url, {"age_max": 20}, format="json").status_code, 400)
        prefs = self.client.get(ME).json()["partner_preference"]
        self.assertEqual((prefs["age_min"], prefs["age_max"], prefs["religions"]), (23, 29, ["hindu"]))


class PhotoTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = make_user()
        self.profile = make_profile(self.user)
        self.client = client_for(self.user)

    def post_photo(self, client=None, **kwargs):
        return (client or self.client).post(PHOTOS, {"photo": upload(**kwargs)}, format="multipart")

    def test_valid_formats_are_reencoded_jpegs(self):
        for fmt, name, content_type in [
            ("JPEG", "holiday.jpg", "image/jpeg"),
            ("PNG", "holiday.png", "image/png"),
            ("WEBP", "holiday.webp", "image/webp"),
        ]:
            with self.subTest(fmt=fmt):
                response = self.post_photo(data=image_bytes(fmt), name=name, content_type=content_type)
                self.assertEqual(response.status_code, 201, response.content)
                photo = ProfilePhoto.objects.get(public_id=response.json()["id"])
                self.assertEqual(photo.status, PhotoStatus.PENDING)
                self.assertTrue(photo.image.name.startswith(f"profile-photos/{self.profile.public_id.hex}/"))
                self.assertTrue(photo.image.name.endswith(".jpg"))
                self.assertNotIn("holiday", photo.image.name)
                with photo.image.open("rb") as stored, Image.open(stored) as image:
                    self.assertEqual(image.format, "JPEG")

        primaries = list(self.profile.photos.filter(is_primary=True))
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0], self.profile.photos.order_by("created_at").first())

    def test_large_images_are_downscaled(self):
        response = self.post_photo(data=image_bytes(size=(3000, 2000)))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(max(response.json()["width"], response.json()["height"]), 1600)

    def test_rejected_uploads(self):
        cases = {
            "not an image": dict(data=b"<?php echo 'hi'; ?>", name="photo.jpg"),
            "gif": dict(data=image_bytes("GIF"), name="photo.gif", content_type="image/gif"),
            "too small": dict(data=image_bytes(size=(100, 120))),
            "truncated": dict(data=image_bytes()[:200]),
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                response = self.post_photo(**kwargs)
                self.assertEqual(response.status_code, 400)
                self.assertIn("photo", response.json())
        missing = self.client.post(PHOTOS, {}, format="multipart")
        self.assertEqual(missing.status_code, 400)
        self.assertFalse(ProfilePhoto.objects.exists())

    @override_settings(PROFILE_PHOTO_MAX_BYTES=1024)
    def test_oversized_upload(self):
        response = self.post_photo()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProfilePhoto.objects.exists())

    @override_settings(PROFILE_MAX_PHOTOS=2)
    def test_photo_limit(self):
        self.assertEqual(self.post_photo().status_code, 201)
        self.assertEqual(self.post_photo().status_code, 201)
        response = self.post_photo()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "photo_limit")

    def test_cannot_touch_another_members_photo(self):
        other_user = make_user()
        make_profile(other_user, gender="female")
        other_client = client_for(other_user)
        photo_id = self.post_photo(client=other_client).json()["id"]

        self.assertEqual(self.client.delete(f"{PHOTOS}{photo_id}/").status_code, 404)
        self.assertEqual(self.client.post(f"{PHOTOS}{photo_id}/primary/").status_code, 404)
        self.assertTrue(ProfilePhoto.objects.filter(public_id=photo_id).exists())

    def test_set_primary_and_delete_primary_promotes_next(self):
        first = self.post_photo().json()["id"]
        second = self.post_photo().json()["id"]
        third = self.post_photo().json()["id"]

        response = self.client.post(f"{PHOTOS}{third}/primary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json() if p["is_primary"]], [third])

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(f"{PHOTOS}{third}/").status_code, 204)
        remaining = self.client.get(PHOTOS).json()
        self.assertEqual({p["id"] for p in remaining}, {first, second})
        self.assertEqual([p["id"] for p in remaining if p["is_primary"]], [first])

    def test_rejected_photo_cannot_be_primary(self):
        self.post_photo()
        photo_id = self.post_photo().json()["id"]
        ProfilePhoto.objects.filter(public_id=photo_id).update(status=PhotoStatus.REJECTED)
        response = self.client.post(f"{PHOTOS}{photo_id}/primary/")
        self.assertEqual(response.status_code, 409)

    def test_signed_photo_url(self):
        self.post_photo()
        url = self.client.get(PHOTOS).json()[0]["url"]
        anonymous = client_for()
        response = anonymous.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"\xff\xd8"))

        tampered = url.rstrip("/")[:-1] + ("A" if not url.rstrip("/").endswith("A") else "B") + "/"
        self.assertEqual(anonymous.get(tampered).status_code, 404)
        self.assertEqual(anonymous.get("/api/v1/profiles/photo-files/garbage/").status_code, 404)

    def test_expired_photo_url(self):
        self.post_photo()
        with override_settings(PHOTO_URL_TTL_SECONDS=-10):
            url = self.client.get(PHOTOS).json()[0]["url"]
        self.assertEqual(client_for().get(url).status_code, 404)

    def test_deleted_photo_url_stops_working(self):
        photo_id = self.post_photo().json()["id"]
        url = self.client.get(PHOTOS).json()[0]["url"]
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(f"{PHOTOS}{photo_id}/")
        self.assertEqual(client_for().get(url).status_code, 404)


def walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


class VisibilityTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.viewer_user = make_user()
        self.viewer = make_profile(self.viewer_user, gender="male")
        self.client = client_for(self.viewer_user)
        self.other_user = make_user()
        self.other = make_profile(self.other_user, gender="female", display_name="Meera")

    def add_photo(self, profile, status=PhotoStatus.APPROVED):
        response = client_for(profile.user).post(PHOTOS, {"photo": upload()}, format="multipart")
        ProfilePhoto.objects.filter(public_id=response.json()["id"]).update(status=status)

    def test_only_active_visible_profiles_are_shown(self):
        self.assertEqual(self.client.get(detail_url(self.other.profile_code)).status_code, 200)
        # Codes are case-insensitive.
        self.assertEqual(self.client.get(detail_url(self.other.profile_code.lower())).status_code, 200)
        for status, visibility in [
            (ProfileStatus.DRAFT, Visibility.MEMBERS),
            (ProfileStatus.PENDING_REVIEW, Visibility.MEMBERS),
            (ProfileStatus.REJECTED, Visibility.MEMBERS),
            (ProfileStatus.SUSPENDED, Visibility.MEMBERS),
            (ProfileStatus.ACTIVE, Visibility.HIDDEN),
        ]:
            with self.subTest(status=status, visibility=visibility):
                Profile.objects.filter(pk=self.other.pk).update(status=status, visibility=visibility)
                self.assertEqual(self.client.get(detail_url(self.other.profile_code)).status_code, 404)

        Profile.objects.filter(pk=self.other.pk).update(status=ProfileStatus.ACTIVE, visibility=Visibility.MEMBERS)
        self.other_user.is_active = False
        self.other_user.save()
        self.assertEqual(self.client.get(detail_url(self.other.profile_code)).status_code, 404)
        self.assertEqual(self.client.get(detail_url("MM999999")).status_code, 404)

    def test_own_profile_always_visible(self):
        Profile.objects.filter(pk=self.viewer.pk).update(status=ProfileStatus.DRAFT, visibility=Visibility.HIDDEN)
        response = self.client.get(detail_url(self.viewer.profile_code))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["viewer"]["is_own_profile"])

    def test_member_without_profile(self):
        response = client_for(make_user()).get(detail_url(self.other.profile_code))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "no_profile")

    def test_no_private_fields(self):
        from apps.memberships.tests import subscribe

        subscribe(self.viewer_user, "silver")  # the career section is part of the full view
        self.other.annual_income = "5l_10l"
        self.other.save()
        response = self.client.get(detail_url(self.other.profile_code))
        body = response.json()
        keys = set(walk_keys(body))
        for private in ["phone_number", "email", "date_of_birth", "user", "id", "public_id"]:
            self.assertNotIn(private, keys)
        text = json.dumps(body)
        self.assertNotIn(self.other_user.email, text)
        self.assertNotIn(self.other_user.phone_number, text)
        self.assertNotIn(str(self.other.date_of_birth), text)
        self.assertEqual(body["career"]["annual_income"], "")

        self.other.income_visible = True
        self.other.save()
        self.assertEqual(
            self.client.get(detail_url(self.other.profile_code)).json()["career"]["annual_income"], "₹5–10 lakh"
        )

    def test_pending_photos_hidden_from_others(self):
        self.add_photo(self.other, status=PhotoStatus.PENDING)
        body = self.client.get(detail_url(self.other.profile_code)).json()
        self.assertIsNone(body["photo"])
        self.assertEqual(body["photos"], [])
        self.assertFalse(body["photos_hidden"])
        # The owner still sees it.
        own = client_for(self.other_user).get(detail_url(self.other.profile_code)).json()
        self.assertEqual(len(own["photos"]), 1)

        ProfilePhoto.objects.filter(profile=self.other).update(status=PhotoStatus.APPROVED)
        body = self.client.get(detail_url(self.other.profile_code)).json()
        self.assertIsNotNone(body["photo"])
        self.assertEqual(len(body["photos"]), 1)

    def test_photos_for_accepted_interests_only(self):
        self.add_photo(self.other)
        Profile.objects.filter(pk=self.other.pk).update(photo_visibility=PhotoVisibility.ACCEPTED)
        body = self.client.get(detail_url(self.other.profile_code)).json()
        self.assertIsNone(body["photo"])
        self.assertEqual(body["photos"], [])
        self.assertTrue(body["photos_hidden"])
        self.assertNotIn("photo-files", json.dumps(body))

        interest = Interest.objects.create(sender=self.viewer, receiver=self.other)
        self.assertIsNone(self.client.get(detail_url(self.other.profile_code)).json()["photo"])
        interest.status = InterestStatus.ACCEPTED
        interest.save()
        body = self.client.get(detail_url(self.other.profile_code)).json()
        self.assertIsNotNone(body["photo"])
        self.assertFalse(body["photos_hidden"])

    def test_viewer_state(self):
        Interest.objects.create(sender=self.viewer, receiver=self.other)
        viewer = self.client.get(detail_url(self.other.profile_code)).json()["viewer"]
        self.assertEqual(viewer["interest_sent"]["status"], "pending")
        self.assertIsNone(viewer["interest_received"])
        self.assertFalse(viewer["shortlisted"])


class MatchesTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.me = make_profile(self.user, gender="male")
        self.client = client_for(self.user)

    def codes(self):
        response = self.client.get(MATCHES)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue({"count", "next", "previous", "results"} <= set(body))
        return {item["profile_code"] for item in body["results"]}

    def test_opposite_gender_active_visible_only(self):
        woman = make_profile(gender="female")
        make_profile(gender="male")
        make_profile(gender="female", status=ProfileStatus.DRAFT)
        make_profile(gender="female", status=ProfileStatus.PENDING_REVIEW)
        make_profile(gender="female", visibility=Visibility.HIDDEN)
        inactive = make_profile(gender="female")
        inactive.user.is_active = False
        inactive.user.save()
        self.assertEqual(self.codes(), {woman.profile_code})

    def test_partner_preferences_filter(self):
        young = make_profile(gender="female", age=24, religion="hindu", marital_status="never_married")
        older = make_profile(gender="female", age=34, religion="hindu", marital_status="never_married")
        christian = make_profile(gender="female", age=25, religion="christian", community="", marital_status="never_married")
        divorced = make_profile(gender="female", age=25, religion="hindu", marital_status="divorced")
        self.assertEqual(self.codes(), {young.profile_code, older.profile_code, christian.profile_code, divorced.profile_code})

        pref = self.me.partner_preference
        pref.age_min, pref.age_max = 22, 30
        pref.religions = ["hindu"]
        pref.marital_statuses = ["never_married"]
        pref.save()
        self.assertEqual(self.codes(), {young.profile_code})

    def test_age_bounds_are_inclusive(self):
        at_min = make_profile(gender="female", age=22)
        at_max = make_profile(gender="female", age=30)
        make_profile(gender="female", age=31)
        make_profile(gender="female", age=21)
        pref = self.me.partner_preference
        pref.age_min, pref.age_max = 22, 30
        pref.save()
        self.assertEqual(self.codes(), {at_min.profile_code, at_max.profile_code})

    def test_requires_profile(self):
        response = client_for(make_user()).get(MATCHES)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "no_profile")

    def test_match_cards_have_no_private_fields(self):
        make_profile(gender="female")
        card = self.client.get(MATCHES).json()["results"][0]
        self.assertFalse({"date_of_birth", "email", "phone_number"} & set(walk_keys(card)))
        self.assertEqual(card["age"], 25)


class DashboardSummaryTests(TestCase):
    URL = "/api/v1/dashboard/summary/"

    def test_member_without_profile(self):
        user = make_user(first_name="Anu")
        body = client_for(user).get(self.URL).json()
        self.assertEqual(body["member"]["first_name"], "Anu")
        self.assertIsNone(body["profile"])
        self.assertIsNone(body["interests"])
        self.assertIsNone(body["membership"])
        self.assertEqual(body["shortlisted"], 0)
        self.assertEqual(body["recent_interests"], [])
        self.assertEqual(body["notifications"]["unread"], 0)

    def test_counts_come_from_records(self):
        from apps.interactions.models import Shortlist
        from apps.memberships.models import Subscription
        from apps.notifications.models import NotificationKind
        from apps.notifications.services import notify

        me = make_profile(gender="male")
        brides = [make_profile(gender="female") for _ in range(6)]
        # Received: 2 pending, 1 accepted, 1 declined, 1 withdrawn (not counted).
        Interest.objects.create(sender=brides[0], receiver=me)
        Interest.objects.create(sender=brides[1], receiver=me)
        Interest.objects.create(sender=brides[2], receiver=me, status=InterestStatus.ACCEPTED)
        Interest.objects.create(sender=brides[3], receiver=me, status=InterestStatus.DECLINED)
        Interest.objects.create(sender=brides[4], receiver=me, status=InterestStatus.WITHDRAWN)
        # Sent: 1 pending, 1 accepted.
        Interest.objects.create(sender=me, receiver=brides[5])
        Interest.objects.create(sender=me, receiver=brides[4], status=InterestStatus.ACCEPTED)
        Shortlist.objects.create(owner=me, profile=brides[0])
        Shortlist.objects.create(owner=me, profile=brides[1])
        notify(me.user, NotificationKind.INTEREST_RECEIVED, "One")
        read = notify(me.user, NotificationKind.INTEREST_RECEIVED, "Two")
        read.read_at = read.created_at
        read.save()
        subscription = Subscription.objects.create(user=me.user, plan_code="diamond")
        subscription.activate()
        subscription.save()

        body = client_for(me.user).get(self.URL).json()
        self.assertEqual(
            body["interests"],
            {"received": 4, "awaiting_your_response": 2, "sent": 2, "sent_pending": 1, "accepted": 2},
        )
        self.assertEqual(body["shortlisted"], 2)
        self.assertEqual(body["notifications"]["unread"], 1)
        self.assertEqual(len(body["notifications"]["recent"]), 2)
        self.assertEqual(body["membership"]["plan_code"], "diamond")
        self.assertEqual(body["profile"]["profile_code"], me.profile_code)
        self.assertIn("percent", body["profile"]["completion"])
        self.assertIsNone(body["profile"]["photo"])

        recent = body["recent_interests"]
        self.assertEqual(len(recent), 5)
        self.assertTrue(all(item["status"] != InterestStatus.WITHDRAWN for item in recent))
        self.assertEqual({item["direction"] for item in recent}, {"sent", "received"})

    def test_summary_is_per_member(self):
        me = make_profile(gender="male")
        someone = make_profile(gender="male")
        bride = make_profile(gender="female")
        Interest.objects.create(sender=bride, receiver=someone)
        body = client_for(me.user).get(self.URL).json()
        self.assertEqual(body["interests"]["received"], 0)
        self.assertEqual(body["recent_interests"], [])


class AgeTests(TestCase):
    def test_age_property(self):
        profile = make_profile(gender="female", age=25)
        self.assertEqual(profile.age, 25)
        self.assertIsInstance(profile.date_of_birth, date)
