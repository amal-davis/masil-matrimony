"""Tiered profile access (apps.profiles.access) on GET /profiles/<code>/ and the endpoints around it."""
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.interactions.models import ContactView
from apps.memberships.models import Subscription, SubscriptionStatus
from apps.memberships.tests import subscribe
from apps.memberships.models import MembershipPackage
from apps.payments.models import Purchase, PurchaseStatus

from .choices import ContactSharing, PhotoStatus, PhotoVisibility, ProfileStatus, Visibility
from .models import ProfilePhoto
from .test_utils import TempMediaMixin, client_for, image_bytes, make_profile, make_user, upload
from .tests import walk_keys

FULL_ONLY = {"about", "native_place", "career", "family", "lifestyle", "partner_preferences"}


def detail(code):
    return f"/api/v1/profiles/{code}/"


class AccessTestCase(TempMediaMixin, TestCase):
    def setUp(self):
        self.owner_user = make_user()
        self.owner = make_profile(
            self.owner_user, gender="female", display_name="Anu Mohan", about="About Anu", native_place="Thrissur",
            father_occupation="Teacher", homepage_consent=True, is_highlighted=True,
            contact_sharing=ContactSharing.PAID_MEMBERS,
        )
        self.photos = [self.add_photo(self.owner, primary=i == 0) for i in range(3)]
        self.viewer_user = make_user()
        self.viewer = make_profile(self.viewer_user, gender="male")
        self.member = client_for(self.viewer_user)

    def add_photo(self, profile, primary=False, status=PhotoStatus.APPROVED):
        photo = ProfilePhoto(profile=profile, width=400, height=500, is_primary=primary, status=status)
        photo.image.save("p.jpg", upload(image_bytes()), save=False)
        photo.save()
        return photo

    def get(self, client, code=None):
        return client.get(detail(code or self.owner.profile_code))


class VisitorTests(AccessTestCase):
    def test_visitor_sees_only_what_public_consent_covers(self):
        response = self.get(APIClient())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["access"], {"level": "public", "reason": "signed_out"})
        self.assertEqual(body["display_name"], "Anu")  # given name only
        self.assertEqual(
            set(body),
            {"profile_code", "display_name", "gender", "age", "education", "location", "photo", "photos",
             "photos_hidden", "access", "viewer"},
        )
        self.assertEqual(len(body["photos"]), 1)
        self.assertIsNone(body["viewer"])
        text = json.dumps(body)
        for secret in ("Mohan", "About Anu", "Teacher", self.owner_user.phone_number, self.owner_user.email):
            self.assertNotIn(secret, text)

    def test_visitor_is_asked_to_sign_in_unless_consented_and_featured(self):
        for consent, featured in ((False, True), (True, False), (False, False)):
            with self.subTest(consent=consent, featured=featured):
                self.owner.homepage_consent, self.owner.is_highlighted = consent, featured
                self.owner.save()
                response = self.get(APIClient())
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["code"], "sign_in_required")
        # An unknown code looks the same, so codes can't be probed.
        self.assertEqual(self.get(APIClient(), "MM000000").json()["code"], "sign_in_required")

    def test_consent_never_overrides_moderation_or_visibility(self):
        for change in ({"status": ProfileStatus.PENDING_REVIEW}, {"status": ProfileStatus.SUSPENDED},
                       {"visibility": Visibility.HIDDEN}):
            with self.subTest(change=change):
                for name, value in change.items():
                    setattr(self.owner, name, value)
                self.owner.save()
                self.assertEqual(self.get(APIClient()).status_code, 401)
                self.owner.status, self.owner.visibility = ProfileStatus.ACTIVE, Visibility.MEMBERS
                self.owner.save()

    def test_visitor_photo_respects_photo_privacy(self):
        self.owner.photo_visibility = PhotoVisibility.ACCEPTED
        self.owner.save()
        body = self.get(APIClient()).json()
        self.assertEqual((body["photo"], body["photos"], body["photos_hidden"]), (None, [], True))

    def test_visitor_cannot_reach_contact_numbers_or_member_lists(self):
        anon = APIClient()
        contact = f"/api/v1/profiles/{self.owner.profile_code}/contact/"
        for method, path in (("get", contact), ("post", contact), ("get", "/api/v1/profiles/search/"),
                             ("get", "/api/v1/profiles/matches/")):
            with self.subTest(path=path, method=method):
                self.assertIn(getattr(anon, method)(path).status_code, (401, 403, 404))

    def test_responses_are_never_shared_by_caches(self):
        for client in (APIClient(), self.member):
            response = self.get(client)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Authorization", response["Vary"])


class FreeMemberTests(AccessTestCase):
    def test_free_member_gets_the_basic_section_and_one_photo(self):
        body = self.get(self.member).json()
        self.assertEqual(body["access"], {"level": "limited", "reason": "no_membership"})
        self.assertFalse(FULL_ONLY & set(body))
        self.assertEqual(len(body["photos"]), 1)
        self.assertEqual(body["display_name"], "Anu Mohan")
        for basic in ("age", "height_cm", "marital_status", "religion", "community", "education", "occupation",
                      "location", "mother_tongue"):
            self.assertIn(basic, body)
        self.assertNotIn("About Anu", json.dumps(body))
        # Free members keep the actions the Free package includes.
        self.assertEqual(body["viewer"]["contact"]["access"], "not_included")
        self.assertIn("interest_sent", body["viewer"])

    def test_only_the_main_photo_is_returned(self):
        body = self.get(self.member).json()
        primary_url = body["photo"]["url"]
        self.assertEqual([p["url"] for p in body["photos"]], [primary_url])

    def test_ineligible_memberships_grant_nothing(self):
        now = timezone.now()
        expired = subscribe(self.viewer_user, "gold", starts_at=now - timedelta(days=400))
        self.assertLess(expired.ends_at, now)
        Subscription.objects.create(user=self.viewer_user, plan_code="diamond")  # pending: never activated
        cancelled = subscribe(self.viewer_user, "silver")
        cancelled.status = SubscriptionStatus.CANCELLED
        cancelled.save()
        upcoming = subscribe(self.viewer_user, "silver", starts_at=now + timedelta(days=3))
        self.assertGreater(upcoming.starts_at, now)
        body = self.get(self.member).json()
        self.assertEqual(body["access"]["level"], "limited")
        self.assertFalse(FULL_ONLY & set(body))

    def test_an_unconfirmed_online_payment_grants_nothing(self):
        package = MembershipPackage.objects.get(code="gold")
        for i, status in enumerate((PurchaseStatus.AWAITING_PAYMENT, PurchaseStatus.AUTHORIZED,
                                    PurchaseStatus.FAILED, PurchaseStatus.NEEDS_REVIEW)):
            Purchase.objects.create(
                reference=f"MMP-TEST-{i}", user=self.viewer_user, package=package, status=status, mode="test",
                package_code="gold", package_name=package.name, validity_months=6, tax_treatment="inclusive",
                base_amount=8000, gst_rate=18, gst_amount=1440, total_amount=9440, amount_subunits=944000,
                billing_email="buyer@example.com",
            )
        self.assertEqual(self.get(self.member).json()["access"]["level"], "limited")

    def test_client_claims_are_ignored(self):
        response = self.member.get(
            detail(self.owner.profile_code), {"is_paid": "1", "has_membership": "true", "user_id": self.owner_user.pk},
            HTTP_X_MEMBERSHIP="gold",
        )
        self.assertEqual(response.json()["access"]["level"], "limited")


class PaidMemberTests(AccessTestCase):
    def test_eligible_package_gets_every_section_and_permitted_photo(self):
        for code in ("silver", "gold", "diamond", "platinum", "royal"):
            with self.subTest(package=code):
                Subscription.objects.filter(user=self.viewer_user).delete()
                subscribe(self.viewer_user, code)
                body = self.get(self.member).json()
                self.assertEqual(body["access"], {"level": "full", "reason": "membership"})
                self.assertTrue(FULL_ONLY <= set(body))
                self.assertEqual(body["about"], "About Anu")
                self.assertEqual(len(body["photos"]), 3)

    def test_unapproved_photos_and_photo_privacy_still_apply(self):
        subscribe(self.viewer_user, "gold")
        self.add_photo(self.owner, status=PhotoStatus.PENDING)
        self.assertEqual(len(self.get(self.member).json()["photos"]), 3)
        self.owner.photo_visibility = PhotoVisibility.ACCEPTED
        self.owner.save()
        body = self.get(self.member).json()
        self.assertEqual((body["photos"], body["photos_hidden"]), ([], True))

    def test_profile_responses_never_contain_contact_details(self):
        subscribe(self.viewer_user, "gold")
        body = self.get(self.member).json()
        keys = set(walk_keys(body))
        self.assertFalse({"phone_number", "email", "date_of_birth"} & keys)
        self.assertNotIn(self.owner_user.phone_number, json.dumps(body))
        self.assertEqual(body["viewer"]["contact"]["access"], "available")


class ContactTests(AccessTestCase):
    def contact(self, code=None):
        return self.member.post(f"/api/v1/profiles/{code or self.owner.profile_code}/contact/")

    def test_contact_needs_a_package_with_a_contact_allowance(self):
        self.assertEqual(self.contact().status_code, 403)  # free
        subscribe(self.viewer_user, "platinum")  # full profile, but its matchmaker coordinates contact
        self.assertEqual(self.get(self.member).json()["access"]["level"], "full")
        response = self.contact()
        self.assertEqual((response.status_code, response.json()["code"]), (403, "not_included"))

    def test_contact_respects_the_owner_choice_and_the_allowance(self):
        subscription = subscribe(self.viewer_user, "silver")
        response = self.contact()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["phone_number"], self.owner_user.phone_number)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.contact().status_code, 200)  # the same member again is free
        subscription.refresh_from_db()
        self.assertEqual(subscription.contact_views_used, 1)
        # Viewing a profile never uses the allowance.
        self.get(self.member)
        subscription.refresh_from_db()
        self.assertEqual(subscription.contact_views_used, 1)

        other = make_profile(gender="female", contact_sharing=ContactSharing.PAID_MEMBERS)
        Subscription.objects.filter(pk=subscription.pk).update(contact_views_used=subscription.contact_view_limit)
        self.assertEqual(self.contact(other.profile_code).json()["code"], "limit_reached")
        self.assertFalse(ContactView.objects.filter(profile=other).exists())

        hidden = make_profile(gender="female", contact_sharing=ContactSharing.HIDDEN)
        self.assertEqual(self.contact(hidden.profile_code).json()["code"], "not_shared")


class OwnProfileTests(AccessTestCase):
    def test_owner_sees_everything_but_public_views_still_follow_their_settings(self):
        own = client_for(self.owner_user)
        body = self.get(own).json()
        self.assertEqual(body["access"], {"level": "full", "reason": "own_profile"})
        self.assertTrue(FULL_ONLY <= set(body))
        # Being the owner doesn't change what anyone else gets.
        self.assertEqual(self.get(APIClient()).json()["access"]["level"], "public")
        self.assertEqual(self.get(self.member).json()["access"]["level"], "limited")


class ListTests(AccessTestCase):
    def test_cards_in_search_carry_no_private_or_full_only_fields(self):
        subscribe(self.viewer_user, "gold")
        body = self.member.get("/api/v1/profiles/search/").json()
        keys = set(walk_keys(body))
        self.assertFalse(FULL_ONLY & keys)
        self.assertFalse({"phone_number", "email", "date_of_birth", "photos"} & keys)
