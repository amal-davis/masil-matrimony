"""
Diamond membership end to end. Diamond shares its feature implementations
with Gold (every Gold test class below runs again with Diamond's terms) and
keeps its own: ₹12,000 + GST, 12 calendar months, 100 contact numbers.
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from apps.interactions import services as interaction_services
from apps.profiles.test_utils import client_for, make_profile, make_user

from . import tests_gold
from .entitlements import FEATURE_PACKAGES, entitlements_for
from .models import MembershipPackage, Subscription, add_months
from .tests import subscribe

IST = ZoneInfo("Asia/Kolkata")
ME = "/api/v1/memberships/me/"


class DiamondPurchaseTests(tests_gold.GoldPurchaseTests):
    # ₹12,000 + 18% GST (the test rate), in paise.
    PLAN, PAISE, FEE, MONTHS, CONTACTS = "diamond", 14160_00, Decimal("12000.00"), 12, 100
    LOWER = "gold"


class DiamondAssistanceTests(tests_gold.AssistanceTests):
    PLAN = "diamond"


class DiamondValidityTests(TestCase):
    def test_twelve_calendar_months_in_india_time(self):
        cases = [
            (datetime(2026, 10, 27, 10, 0, tzinfo=IST), datetime(2027, 10, 27, 10, 0, tzinfo=IST)),
            # 29 February has no match a year later: the last day of February.
            (datetime(2028, 2, 29, 10, 0, tzinfo=IST), datetime(2029, 2, 28, 10, 0, tzinfo=IST)),
            (datetime(2026, 1, 31, 23, 59, tzinfo=IST), datetime(2027, 1, 31, 23, 59, tzinfo=IST)),
            # 00:30 on 1 January in India is still 31 December in UTC: the Indian date counts.
            (datetime(2026, 12, 31, 19, 0, tzinfo=dt_timezone.utc), datetime(2028, 1, 1, 0, 30, tzinfo=IST)),
        ]
        for start, end in cases:
            with self.subTest(start=start):
                self.assertEqual(add_months(start, 12), end)
        # Not 365 days: across a leap day, 365 days falls a day short.
        start = datetime(2027, 3, 1, 10, 0, tzinfo=IST)
        self.assertEqual((start + timedelta(days=365)).date().isoformat(), "2028-02-29")
        self.assertEqual(add_months(start, 12).date().isoformat(), "2028-03-01")

    def test_activated_diamond_uses_its_twelve_months(self):
        subscription = subscribe(make_user(), "diamond", starts_at=datetime(2028, 2, 29, 10, 0, tzinfo=IST))
        self.assertEqual((subscription.validity_months, subscription.contact_view_limit), (12, 100))
        self.assertEqual(subscription.ends_at, datetime(2029, 2, 28, 10, 0, tzinfo=IST))

    def test_expired_or_cancelled_diamond_grants_nothing(self):
        for change in ({"ends_at": timezone.now() - timedelta(seconds=1)}, {"status": "cancelled"}):
            with self.subTest(change=change):
                user = make_user()
                subscription = subscribe(user, "diamond")
                Subscription.objects.filter(pk=subscription.pk).update(**change)
                entitlements = client_for(user).get(ME).json()["entitlements"]
                self.assertEqual(entitlements["package_code"], "free")
                self.assertFalse(any(entitlements["features"][f] for f in FEATURE_PACKAGES))
                self.assertIsNone(entitlements["contact_view_limit"])


class DiamondTermsTests(TestCase):
    def test_package_row_and_public_listing(self):
        package = MembershipPackage.objects.get(code="diamond")
        self.assertEqual(
            (package.fee, package.tax_treatment, package.validity_months, package.contact_view_limit,
             package.outgoing_interest_limit),
            (Decimal("12000"), "gst_extra", 12, 100, None),
        )
        listed = next(item for item in client_for().get("/api/v1/memberships/packages/").json() if item["code"] == "diamond")
        self.assertEqual((listed["fee"], listed["validity_months"], listed["contact_view_limit"]), ("12000.00", 12, 100))

    def test_allowance_is_diamonds_own_not_carried_from_an_earlier_membership(self):
        """After a used-up Silver ends, Diamond starts its own count of 100."""
        groom = make_profile(gender="male")
        silver = subscribe(groom.user, "silver")
        bride = make_profile(gender="female", contact_sharing="paid_members")
        interaction_services.view_contact(groom, bride.profile_code)
        Subscription.objects.filter(pk=silver.pk).update(
            contact_views_used=40, ends_at=timezone.now() - timedelta(seconds=1)
        )
        diamond = subscribe(groom.user, "diamond")
        entitlements = entitlements_for(groom.user)
        self.assertEqual(entitlements.subscription, diamond)
        self.assertEqual((entitlements.contact_view_limit, entitlements.contact_views_remaining), (100, 100))
        # The number viewed under Silver is a new unlock under Diamond, counted once.
        interaction_services.view_contact(groom, bride.profile_code)
        diamond.refresh_from_db()
        silver.refresh_from_db()
        self.assertEqual((diamond.contact_views_used, silver.contact_views_used), (1, 40))

    def test_dashboard_shows_diamond_as_the_backend_decided(self):
        user = make_user()
        make_profile(user, gender="male")
        subscription = subscribe(user, "diamond")
        Subscription.objects.filter(pk=subscription.pk).update(contact_views_used=25)
        client = client_for(user)
        summary = client.get("/api/v1/dashboard/summary/").json()
        me = client.get(ME).json()
        self.assertEqual(summary["entitlements"], me["entitlements"])
        self.assertEqual((me["current"]["plan_code"], me["current"]["status"]), ("diamond", "active"))
        self.assertEqual(
            (me["entitlements"]["contact_views_used"], me["entitlements"]["contact_views_remaining"]), (25, 75)
        )
        self.assertTrue(all(me["entitlements"]["features"].values()))
        self.assertEqual(me["assistance"], {"included": True, "can_request": True, "available": True, "requests": []})


class DiamondVerificationTests(TestCase):
    def test_diamond_may_ask_but_only_staff_verify(self):
        from apps.profiles import verification
        from apps.accounts.roles import Role

        bride = make_profile(gender="female")
        groom = make_profile(gender="male")
        subscribe(bride.user, "diamond")
        detail = f"/api/v1/profiles/{bride.profile_code}/"
        self.assertFalse(client_for(groom.user).get(detail).json()["verified"])  # paying verifies nobody

        response = client_for(bride.user).post("/api/v1/profiles/me/verification/")
        self.assertEqual((response.status_code, response.json()["verification_status"]), (200, "requested"))
        self.assertFalse(client_for(groom.user).get(detail).json()["verified"])  # asking verifies nobody

        verification.decide(bride, make_user(Role.ADMIN, is_staff=True), verified=True)
        self.assertTrue(client_for(groom.user).get(detail).json()["verified"])
