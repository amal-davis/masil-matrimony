from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import TestCase
from django.utils import timezone

from apps.profiles.test_utils import client_for, make_user

from .models import Subscription, SubscriptionStatus, add_months
from .plans import PLANS, PlanCode

URL = "/api/v1/memberships/me/"


class AddMonthsTests(TestCase):
    def test_add_months(self):
        start = datetime(2026, 1, 31, 10, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(add_months(start, 1), datetime(2026, 2, 28, 10, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(add_months(start, 12), datetime(2027, 1, 31, 10, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(add_months(datetime(2026, 11, 15, tzinfo=dt_timezone.utc), 3).month, 2)


class MembershipApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = client_for(self.user)

    def test_no_subscription(self):
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"], [])
        self.assertIs(body["online_payment_available"], False)

    def test_pending_subscription_grants_nothing(self):
        Subscription.objects.create(user=self.user, plan_code=PlanCode.DIAMOND)
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(len(body["history"]), 1)
        self.assertEqual(body["history"][0]["status"], "pending")
        self.assertIsNone(body["history"][0]["ends_at"])

    def test_activation_sets_validity_period(self):
        for code, plan in PLANS.items():
            with self.subTest(plan=code):
                subscription = Subscription.objects.create(user=self.user, plan_code=code)
                start = timezone.now()
                subscription.activate(starts_at=start)
                subscription.save()
                self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
                self.assertEqual(subscription.ends_at, add_months(start, plan.validity_months))
                self.assertTrue(subscription.is_current)

        self.assertEqual(PLANS[PlanCode.DIAMOND].validity_months, 12)
        self.assertEqual(PLANS[PlanCode.PLATINUM].validity_months, 3)
        self.assertEqual(PLANS[PlanCode.ROYAL].validity_months, 12)
        self.assertEqual(PLANS[PlanCode.DIAMOND].contact_view_limit, 100)

    def test_current_subscription(self):
        subscription = Subscription.objects.create(user=self.user, plan_code=PlanCode.DIAMOND)
        subscription.activate()
        subscription.save()
        current = self.client.get(URL).json()["current"]
        self.assertEqual(current["plan_code"], "diamond")
        self.assertEqual(current["status"], "active")
        self.assertEqual(current["contact_view_limit"], 100)
        self.assertEqual(current["contact_views_used"], 0)

    def test_expired_subscription(self):
        subscription = Subscription.objects.create(user=self.user, plan_code=PlanCode.PLATINUM)
        subscription.activate(starts_at=timezone.now() - timedelta(days=200))
        subscription.save()
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"][0]["status"], "expired")

    def test_cancelled_subscription(self):
        subscription = Subscription.objects.create(user=self.user, plan_code=PlanCode.ROYAL)
        subscription.activate()
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.save()
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"][0]["status"], "cancelled")

    def test_only_own_subscriptions(self):
        other = make_user()
        subscription = Subscription.objects.create(user=other, plan_code=PlanCode.DIAMOND)
        subscription.activate()
        subscription.save()
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"], [])
