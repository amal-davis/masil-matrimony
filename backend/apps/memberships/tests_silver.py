"""
Silver membership end to end: buying it (Razorpay mocked), its three calendar
months, and every entitlement it grants or stops granting, next to the other
packages, which must keep their own terms.
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.payments.models import Purchase, PurchaseStatus
from apps.payments.tests import PURCHASES, PaymentsTestCase
from apps.profiles.test_utils import client_for, make_profile, make_user

from .entitlements import FEATURE_PACKAGES, Feature, entitlements_for
from .models import Subscription, add_months
from .tests import subscribe

IST = ZoneInfo("Asia/Kolkata")
ME = "/api/v1/memberships/me/"
SILVER_PAISE = 5900_00  # ₹5,000 + 18% GST, with the test rate below


@override_settings(MEMBERSHIP_GST_RATE_PERCENT="18")
class SilverPurchaseTests(PaymentsTestCase):
    def pay_for_silver(self, client=None, status="captured"):
        response = (client or self.client).post(PURCHASES, {"package": "silver"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        purchase = Purchase.objects.get(reference=response.json()["purchase"]["reference"])
        payment_id = self.razorpay.pay(purchase.razorpay_order_id, status=status)
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, payment_id, client=client)
        purchase.refresh_from_db()
        return purchase

    def test_paid_silver_activates_for_this_member_only(self):
        other = make_user()
        purchase = self.pay_for_silver()
        self.assertEqual((purchase.status, purchase.amount_subunits), (PurchaseStatus.PAID, SILVER_PAISE))
        self.assertEqual(purchase.base_amount, Decimal("5000.00"))  # GST added once, on top of the fee

        subscription = purchase.subscription
        self.assertEqual((subscription.user, subscription.plan_code), (self.user, "silver"))
        self.assertEqual(subscription.validity_months, 3)
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, 3))
        self.assertEqual((subscription.contact_view_limit, subscription.contact_views_used), (40, 0))

        body = self.client.get(ME).json()
        self.assertEqual(body["current"]["plan_code"], "silver")
        entitlements = body["entitlements"]
        self.assertEqual(entitlements["package_code"], "silver")
        gold_only = {Feature.PRIORITY_VISIBILITY, Feature.MATCHMAKING_ASSISTANCE}
        self.assertEqual({f for f, on in entitlements["features"].items() if not on}, gold_only)
        self.assertEqual(
            (entitlements["contact_view_limit"], entitlements["contact_views_used"], entitlements["contact_views_remaining"]),
            (40, 0, 40),
        )
        self.assertIsNone(entitlements["outgoing_interest_limit"])
        # Nobody else got anything.
        self.assertTrue(entitlements_for(other).is_free)

    def test_unpaid_failed_or_authorized_purchases_grant_nothing(self):
        response = self.client.post(PURCHASES, {"package": "silver"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get(ME).json()["entitlements"]["package_code"], "free")
        for status in ("failed", "authorized"):
            with self.subTest(status=status):
                purchase = Purchase.objects.get()
                self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id, status=status))
                body = self.client.get(ME).json()
                self.assertEqual(body["entitlements"]["package_code"], "free")
                self.assertFalse(any(body["entitlements"]["features"][f] for f in FEATURE_PACKAGES))
        self.assertFalse(Subscription.objects.exists())

    def test_duplicate_notifications_activate_silver_once(self):
        purchase = self.pay_for_silver()
        payment_id = purchase.razorpay_payment_id
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, payment_id)
            for event_id in ("evt_1", "evt_1", "evt_2"):
                self.assertEqual(self.webhook(self.event(purchase, payment_id=payment_id), event_id=event_id).status_code, 200)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_the_request_cannot_choose_another_package_or_price(self):
        response = self.client.post(
            PURCHASES, {"package": "silver", "plan_code": "diamond", "amount": 100, "total": "1.00"}, format="json"
        )
        purchase = Purchase.objects.get(reference=response.json()["purchase"]["reference"])
        self.assertEqual((purchase.package_code, purchase.amount_subunits), ("silver", SILVER_PAISE))


class SilverValidityTests(TestCase):
    def test_three_calendar_months_in_india_time(self):
        cases = [
            (datetime(2026, 10, 27, 10, 0, tzinfo=IST), datetime(2027, 1, 27, 10, 0, tzinfo=IST)),
            # Month ends: the last day of a shorter month, leap years counted.
            (datetime(2026, 11, 30, 10, 0, tzinfo=IST), datetime(2027, 2, 28, 10, 0, tzinfo=IST)),
            (datetime(2027, 11, 30, 10, 0, tzinfo=IST), datetime(2028, 2, 29, 10, 0, tzinfo=IST)),
            (datetime(2026, 8, 31, 23, 59, tzinfo=IST), datetime(2026, 11, 30, 23, 59, tzinfo=IST)),
            # 01:30 on 30 November in India is still 29 November in UTC: the Indian date counts.
            (datetime(2026, 11, 29, 20, 0, tzinfo=dt_timezone.utc), datetime(2027, 2, 28, 1, 30, tzinfo=IST)),
        ]
        for start, end in cases:
            with self.subTest(start=start):
                self.assertEqual(add_months(start, 3), end)
        # Not a 90-day approximation: 27 October + 90 days would be 25 January.
        start = datetime(2026, 10, 27, 10, 0, tzinfo=IST)
        self.assertEqual((start + timedelta(days=90)).date().isoformat(), "2027-01-25")
        self.assertEqual(add_months(start, 3).date().isoformat(), "2027-01-27")

    def test_activated_silver_uses_its_three_months(self):
        start = datetime(2026, 11, 30, 10, 0, tzinfo=IST)
        subscription = subscribe(make_user(), "silver", starts_at=start)
        self.assertEqual(subscription.ends_at, datetime(2027, 2, 28, 10, 0, tzinfo=IST))


class EntitlementsByPackageTests(TestCase):
    """Silver's benefits aren't copied to packages whose published benefits don't include them."""

    EXPECTED = {
        # package: (photo viewing, online features, contact limit, interest limit)
        "free": (False, False, None, 15),
        "silver": (True, True, 40, None),
        "gold": (True, True, 100, None),
        "diamond": (True, True, 100, None),
        "platinum": (True, False, None, None),
        "royal": (True, False, None, None),
    }
    ONLINE = (Feature.ADVANCED_SEARCH, Feature.MESSAGING, Feature.PROFILE_VIEWERS, Feature.VERIFICATION)

    def test_each_package_keeps_its_own_benefits(self):
        for code, (photos, online, contacts, interests) in self.EXPECTED.items():
            with self.subTest(package=code):
                user = make_user()
                if code != "free":
                    subscribe(user, code)
                features = client_for(user).get(ME).json()["entitlements"]
                self.assertEqual(features["package_code"], code)
                self.assertIs(features["features"][Feature.PHOTO_VIEWING], photos)
                for feature in self.ONLINE:
                    self.assertIs(features["features"][feature], online, feature)
                self.assertEqual(features["contact_view_limit"], contacts)
                self.assertIs(features["features"]["contact_access"], contacts is not None)
                self.assertEqual(features["outgoing_interest_limit"], interests)
                # Open to every member.
                self.assertTrue(features["features"]["shortlist"] and features["features"]["match_suggestions"])

    def test_expired_silver_grants_no_paid_entitlement(self):
        user = make_user()
        make_profile(user, gender="male")
        subscription = subscribe(user, "silver", starts_at=timezone.now() - timedelta(days=200))
        self.assertFalse(subscription.is_current)
        entitlements = client_for(user).get(ME).json()["entitlements"]
        self.assertEqual(entitlements["package_code"], "free")
        self.assertFalse(any(entitlements["features"][f] for f in FEATURE_PACKAGES))
        self.assertIsNone(entitlements["contact_view_limit"])
        self.assertEqual(entitlements["outgoing_interest_limit"], 15)

    def test_existing_accounts_get_nothing_without_a_current_membership(self):
        user = make_user()
        make_profile(user)
        Subscription.objects.create(user=user, plan_code="silver")  # recorded, never activated
        self.assertTrue(entitlements_for(user).is_free)
        self.assertFalse(any(entitlements_for(user).has(feature) for feature in FEATURE_PACKAGES))


class DashboardMatchesEntitlementsTests(TestCase):
    def test_dashboard_shows_what_the_backend_decided(self):
        user = make_user()
        make_profile(user, gender="male")
        client = client_for(user)
        for code in ("free", "silver"):
            with self.subTest(package=code):
                if code != "free":
                    subscribe(user, code)
                summary = client.get("/api/v1/dashboard/summary/").json()
                self.assertEqual(summary["entitlements"], client.get(ME).json()["entitlements"])
        summary = client.get("/api/v1/dashboard/summary/").json()
        self.assertEqual(summary["membership"]["plan_code"], "silver")
        self.assertEqual(summary["entitlements"]["contact_views_remaining"], 40)
