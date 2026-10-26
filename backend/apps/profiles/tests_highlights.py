"""Homepage Highlighted Profiles: admin controls, eligibility, the public API and privacy."""
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role

from . import services
from .choices import PhotoStatus, PhotoVisibility, ProfileStatus, Visibility
from .models import Profile
from .test_utils import TempMediaMixin, client_for, make_profile, make_user, upload
from .tests import walk_keys

URL = "/api/v1/profiles/highlighted/"


def featured(**fields):
    """An approved profile, highlighted by staff, whose member agreed to be featured."""
    fields.setdefault("is_highlighted", True)
    fields.setdefault("homepage_consent", True)
    return make_profile(**fields)


class HighlightedApiTests(TestCase):
    def codes(self, **params):
        response = client_for().get(URL, params)
        self.assertEqual(response.status_code, 200)
        return [item["profile_code"] for item in response.json()]

    def test_highlighted_eligible_profile_is_public(self):
        profile = featured(display_name="Anjali Menon", city="Kochi", state="Kerala", highest_education="M.Sc")
        body = client_for().get(URL).json()
        self.assertEqual(body, [{
            "profile_code": profile.profile_code, "given_name": "Anjali", "gender": profile.gender,
            "age": profile.age, "education": "M.Sc",
            "location": {"city": "Kochi", "district": profile.district, "state": "Kerala"}, "photo": None,
        }])

    def test_not_highlighted_or_not_consented_profiles_are_excluded(self):
        make_profile()  # neither
        featured(is_highlighted=False)
        featured(homepage_consent=False)  # staff highlight alone never makes a profile public
        self.assertEqual(self.codes(), [])

    def test_ineligible_profiles_are_excluded(self):
        for status in (ProfileStatus.DRAFT, ProfileStatus.PENDING_REVIEW, ProfileStatus.REJECTED, ProfileStatus.SUSPENDED):
            featured(status=status)
        featured(visibility=Visibility.HIDDEN)
        inactive = featured()
        inactive.user.is_active = False
        inactive.user.save()
        self.assertEqual(self.codes(), [])

    def test_removing_the_highlight_takes_effect_on_the_next_request(self):
        profile = featured()
        self.assertEqual(self.codes(), [profile.profile_code])
        Profile.objects.filter(pk=profile.pk).update(is_highlighted=False)
        self.assertEqual(self.codes(), [])
        Profile.objects.filter(pk=profile.pk).update(is_highlighted=True, homepage_consent=False)
        self.assertEqual(self.codes(), [])

    def test_ordering_is_deterministic(self):
        late = featured(highlight_order=5)
        first = featured(highlight_order=1)
        older = featured(highlight_order=3)
        newer = featured(highlight_order=3)
        Profile.objects.filter(pk=older.pk).update(reviewed_at=timezone.now() - timezone.timedelta(days=5))
        Profile.objects.filter(pk=newer.pk).update(reviewed_at=timezone.now())
        expected = [first.profile_code, newer.profile_code, older.profile_code, late.profile_code]
        self.assertEqual(self.codes(), expected)
        self.assertEqual(self.codes(), expected)

    def test_limit_and_empty_results(self):
        self.assertEqual(client_for().get(URL).json(), [])
        for _ in range(14):
            featured()
        self.assertEqual(len(self.codes()), 12)
        self.assertEqual(len(self.codes(limit=3)), 3)
        self.assertEqual(len(self.codes(limit=500)), 12)
        self.assertEqual(len(self.codes(limit="abc")), 12)

    def test_no_private_fields(self):
        featured(display_name="Anjali Menon", annual_income="10l_20l", income_visible=True)
        card = client_for().get(URL).json()[0]
        private = {"email", "phone_number", "date_of_birth", "display_name", "annual_income", "about", "review_note",
                   "contact_sharing", "partner_preference", "user", "public_id", "is_highlighted", "homepage_consent"}
        self.assertFalse(private & set(walk_keys(card)))
        self.assertNotIn("Menon", str(card))

    def test_query_count_does_not_grow_with_profiles(self):
        featured()

        def count():
            with CaptureQueriesContext(connection) as queries:
                client_for().get(URL)
            return len(queries)

        few = count()
        for _ in range(5):
            featured()
        self.assertEqual(count(), few)

    def test_read_only(self):
        self.assertEqual(client_for().post(URL, {}).status_code, 405)


class PublicPhotoTests(TempMediaMixin, TestCase):
    def test_only_approved_photos_visible_to_all_members_are_shown(self):
        open_photos = featured()
        services.add_photo(open_photos, upload())
        pending = featured()
        services.add_photo(pending, upload())  # not approved yet
        private = featured(photo_visibility=PhotoVisibility.ACCEPTED)
        services.add_photo(private, upload())
        for profile in (open_photos, private):
            profile.photos.update(status=PhotoStatus.APPROVED)

        cards = {item["profile_code"]: item for item in client_for().get(URL).json()}
        self.assertIsNotNone(cards[open_photos.profile_code]["photo"])
        self.assertIn("/photo-files/", cards[open_photos.profile_code]["photo"]["url"])
        self.assertIsNone(cards[pending.profile_code]["photo"])
        self.assertIsNone(cards[private.profile_code]["photo"])


class MemberCantHighlightTests(TestCase):
    def test_member_api_controls_consent_but_not_the_highlight(self):
        user = make_user()
        profile = make_profile(user)
        client = client_for(user)
        response = client.patch(
            "/api/v1/profiles/me/", {"is_highlighted": True, "highlight_order": 0, "homepage_consent": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["homepage_consent"])
        self.assertNotIn("is_highlighted", response.json())
        profile.refresh_from_db()
        self.assertEqual((profile.is_highlighted, profile.homepage_consent), (False, True))


class AdminTests(TestCase):
    def setUp(self):
        self.profile = make_profile(homepage_consent=True)
        self.changelist = reverse("admin:profiles_profile_changelist")

    def staff(self, *perms):
        user = make_user(role=Role.ADMIN, is_staff=True)
        for codename in perms:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        return user

    def act(self, action):
        return self.client.post(self.changelist, {"action": action, "_selected_action": [self.profile.pk]}, follow=True)

    def test_superuser_highlights_and_removes(self):
        self.client.force_login(make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True))
        self.act("highlight")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_highlighted)
        self.assertEqual(len(client_for().get(URL).json()), 1)
        page = self.client.get(self.changelist + "?is_highlighted__exact=1")
        self.assertContains(page, self.profile.profile_code)
        self.act("remove_highlight")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_highlighted)
        self.assertEqual(client_for().get(URL).json(), [])

    def test_highlighting_an_ineligible_profile_warns_and_stays_hidden(self):
        self.client.force_login(make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True))
        Profile.objects.filter(pk=self.profile.pk).update(homepage_consent=False, status=ProfileStatus.PENDING_REVIEW)
        response = self.act("highlight")
        self.assertContains(response, "won&#x27;t appear on the homepage")
        self.assertContains(response, "hasn&#x27;t agreed to be featured")
        self.profile.refresh_from_db()
        # Highlighting never approves or publishes anything.
        self.assertEqual((self.profile.is_highlighted, self.profile.status), (True, ProfileStatus.PENDING_REVIEW))
        self.assertEqual(client_for().get(URL).json(), [])

    def test_change_profile_permission_alone_cannot_highlight(self):
        self.client.force_login(self.staff("view_profile", "change_profile"))
        self.act("highlight")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_highlighted)
        page = self.client.get(reverse("admin:profiles_profile_change", args=[self.profile.pk]))
        self.assertNotContains(page, 'name="is_highlighted"')

    def test_highlight_permission_allows_it(self):
        self.client.force_login(self.staff("view_profile", "change_profile", "highlight_profile"))
        self.act("highlight")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_highlighted)
        page = self.client.get(reverse("admin:profiles_profile_change", args=[self.profile.pk]))
        self.assertContains(page, 'name="is_highlighted"')
        # The member's own consent is never editable by staff.
        self.assertNotContains(page, 'name="homepage_consent"')
