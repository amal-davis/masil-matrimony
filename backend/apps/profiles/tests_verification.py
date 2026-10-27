"""The Verified Profile badge (apps.profiles.verification): requested by eligible members, decided by staff."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import Role
from apps.memberships.tests import subscribe
from apps.notifications.models import Notification

from .choices import ProfileStatus, VerificationStatus
from .models import Profile
from .test_utils import client_for, make_profile, make_user

REQUEST = "/api/v1/profiles/me/verification/"


class VerificationTests(TestCase):
    def setUp(self):
        self.bride = make_profile(gender="female")
        self.groom = make_profile(gender="male")
        self.bride_client = client_for(self.bride.user)
        self.groom_client = client_for(self.groom.user)
        self.staff = make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True)

    def badge_seen_by_groom(self) -> tuple[bool, bool]:
        detail = self.groom_client.get(f"/api/v1/profiles/{self.bride.profile_code}/").json()
        card = self.groom_client.get("/api/v1/profiles/search/").json()["results"][0]
        return detail["verified"], card["verified"]

    def admin_action(self, action, **extra):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse("admin:profiles_profile_changelist"), {"action": action, "_selected_action": [self.bride.pk], **extra}
        )

    def test_unverified_profiles_have_no_badge_even_after_paying(self):
        self.assertEqual(self.badge_seen_by_groom(), (False, False))
        subscribe(self.bride.user, "silver")
        self.assertEqual(self.badge_seen_by_groom(), (False, False))
        self.assertEqual(self.bride_client.get("/api/v1/profiles/me/").json()["verification_status"], "not_requested")

    def test_free_members_cannot_request(self):
        response = self.bride_client.post(REQUEST)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "upgrade_required"))
        self.bride.refresh_from_db()
        self.assertEqual(self.bride.verification_status, VerificationStatus.NOT_REQUESTED)

    def test_silver_request_then_staff_verification_shows_the_badge(self):
        subscribe(self.bride.user, "silver")
        body = self.bride_client.post(REQUEST).json()
        self.assertEqual(body["verification_status"], "requested")
        self.assertEqual(self.bride_client.post(REQUEST).json()["code"], "already_requested")
        self.assertEqual(self.badge_seen_by_groom(), (False, False))  # asking isn't being verified

        self.admin_action("mark_verified")
        self.bride.refresh_from_db()
        self.assertEqual((self.bride.verification_status, self.bride.verified_by), (VerificationStatus.VERIFIED, self.staff))
        self.assertIsNotNone(self.bride.verified_at)
        self.assertTrue(Notification.objects.filter(recipient=self.bride.user, kind="verification_decided").exists())
        self.assertEqual(self.badge_seen_by_groom(), (True, True))
        self.assertEqual(self.bride_client.post(REQUEST).json()["code"], "already_verified")

    def test_staff_can_decline_with_a_note_and_the_member_may_ask_again(self):
        subscribe(self.bride.user, "gold")
        self.bride_client.post(REQUEST)
        Profile.objects.filter(pk=self.bride.pk).update(verification_note="The ID photo was unreadable.")
        self.admin_action("decline_verification")
        own = self.bride_client.get("/api/v1/profiles/me/").json()
        self.assertEqual((own["verification_status"], own["verification_note"]), ("declined", "The ID photo was unreadable."))
        self.assertEqual(self.badge_seen_by_groom(), (False, False))
        self.assertEqual(self.bride_client.post(REQUEST).json()["verification_status"], "requested")

    def test_staff_cannot_verify_without_a_request_or_an_approved_profile(self):
        self.admin_action("mark_verified")
        self.bride.refresh_from_db()
        self.assertEqual(self.bride.verification_status, VerificationStatus.NOT_REQUESTED)

        subscribe(self.bride.user, "silver")
        self.bride_client.post(REQUEST)
        Profile.objects.filter(pk=self.bride.pk).update(status=ProfileStatus.SUSPENDED)
        self.admin_action("mark_verified")
        self.bride.refresh_from_db()
        self.assertEqual(self.bride.verification_status, VerificationStatus.REQUESTED)

    def test_members_cannot_set_their_own_status(self):
        subscribe(self.bride.user, "silver")
        self.bride_client.patch(
            "/api/v1/profiles/me/", {"verification_status": "verified", "verified_at": "2026-01-01T00:00:00Z"},
            format="json",
        )
        self.bride.refresh_from_db()
        self.assertEqual((self.bride.verification_status, self.bride.verified_at), (VerificationStatus.NOT_REQUESTED, None))

    def test_unapproved_profiles_cannot_request(self):
        subscribe(self.bride.user, "silver")
        Profile.objects.filter(pk=self.bride.pk).update(status=ProfileStatus.PENDING_REVIEW)
        self.assertEqual(self.bride_client.post(REQUEST).json()["code"], "profile_not_active")
