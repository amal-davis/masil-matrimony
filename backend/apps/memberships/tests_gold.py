"""
Gold membership end to end: buying it (Razorpay mocked), its six calendar
months, the entitlements it grants (and stops granting), matchmaking
assistance, and the other packages keeping their own terms.
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.admin.sites import site
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.accounts.roles import Role
from apps.notifications.models import Notification
from apps.payments.models import Purchase, PurchaseStatus
from apps.payments.tests import PURCHASES, PaymentsTestCase
from apps.profiles.choices import ProfileStatus
from apps.profiles.test_utils import client_for, make_profile, make_user

from . import assistance
from .entitlements import FEATURE_PACKAGES, Feature, entitlements_for
from .models import AssistanceEvent, AssistanceRequest, AssistanceStatus, MembershipPackage, Subscription, add_months
from .tests import subscribe

IST = ZoneInfo("Asia/Kolkata")


def make_staff(*perms, **fields):
    """
    An active staff account with the "Matchmakers" group's case permissions;
    add "assign" for the "Matchmaking managers" permission to assign cases too.
    """
    from django.contrib.auth.models import Permission

    from apps.accounts.management.commands.sync_admin_groups import MATCHMAKING_CASE_WORK

    user = make_user(Role.ADMIN, is_staff=True, **fields)
    codenames = [perm.split(".")[1] for perm in MATCHMAKING_CASE_WORK] + [
        "assign_assistancerequest" for perm in perms if perm == "assign"
    ]
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="memberships", codename__in=codenames))
    return type(user).objects.get(pk=user.pk)  # fresh permission cache


def inline_management(item) -> dict:
    """The inline formsets' management data on the case's admin change form (no new rows)."""
    data = {}
    for prefix, rows in (("notes", item.notes), ("follow_ups", item.follow_ups), ("candidates", item.candidates),
                         ("exchanges", item.exchanges), ("events", item.events)):
        ids = list(rows.values_list("pk", flat=True))
        data.update({f"{prefix}-TOTAL_FORMS": str(len(ids)), f"{prefix}-INITIAL_FORMS": str(len(ids)),
                     f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
        for index, pk in enumerate(ids):
            data.update({f"{prefix}-{index}-id": str(pk), f"{prefix}-{index}-request": str(item.pk)})
    return data
ME = "/api/v1/memberships/me/"
ASSISTANCE = "/api/v1/memberships/me/assistance/"
GOLD_PAISE = 9440_00  # ₹8,000 + 18% GST, with the test rate below
GOLD_FEATURES = {
    Feature.PHOTO_VIEWING, Feature.ADVANCED_SEARCH, Feature.MESSAGING, Feature.PROFILE_VIEWERS,
    Feature.VERIFICATION, Feature.PRIORITY_VISIBILITY, Feature.MATCHMAKING_ASSISTANCE,
}


@override_settings(MEMBERSHIP_GST_RATE_PERCENT="18")
class GoldPurchaseTests(PaymentsTestCase):
    """Run again for Diamond by DiamondPurchaseTests (tests_diamond.py) with its own terms."""

    PLAN, PAISE, FEE, MONTHS, CONTACTS = "gold", GOLD_PAISE, Decimal("8000.00"), 6, 100
    # A current lower membership that must not be replaced by buying this one.
    LOWER = "silver"

    def pay_for_gold(self, status="captured"):
        response = self.client.post(PURCHASES, {"package": self.PLAN}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        purchase = Purchase.objects.get(reference=response.json()["purchase"]["reference"])
        payment_id = self.razorpay.pay(purchase.razorpay_order_id, status=status)
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, payment_id)
        purchase.refresh_from_db()
        return purchase

    def test_paid_gold_activates_six_months_for_this_member_only(self):
        other = make_user()
        purchase = self.pay_for_gold()
        self.assertEqual((purchase.status, purchase.amount_subunits), (PurchaseStatus.PAID, self.PAISE))
        self.assertEqual(purchase.base_amount, self.FEE)  # GST added once, on top of the fee

        subscription = purchase.subscription
        self.assertEqual(
            (subscription.user, subscription.plan_code, subscription.validity_months), (self.user, self.PLAN, self.MONTHS)
        )
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, self.MONTHS))
        self.assertEqual((subscription.contact_view_limit, subscription.contact_views_used), (self.CONTACTS, 0))

        entitlements = self.client.get(ME).json()["entitlements"]
        self.assertEqual(entitlements["package_code"], self.PLAN)
        self.assertTrue(all(entitlements["features"].values()), entitlements["features"])
        self.assertEqual(entitlements["unavailable"], [])
        self.assertEqual(
            (entitlements["contact_view_limit"], entitlements["contact_views_remaining"]), (self.CONTACTS, self.CONTACTS)
        )
        self.assertIsNone(entitlements["outgoing_interest_limit"])
        self.assertTrue(entitlements_for(other).is_free)

    def test_unpaid_or_failed_gold_grants_nothing(self):
        self.client.post(PURCHASES, {"package": self.PLAN}, format="json")
        self.assertEqual(self.client.get(ME).json()["entitlements"]["package_code"], "free")
        purchase = Purchase.objects.get()
        for status in ("failed", "authorized"):
            with self.subTest(status=status):
                self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id, status=status))
                features = self.client.get(ME).json()["entitlements"]["features"]
                self.assertFalse(any(features[f] for f in FEATURE_PACKAGES))
        self.assertFalse(Subscription.objects.exists())

    def test_duplicate_notifications_activate_gold_once(self):
        purchase = self.pay_for_gold()
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, purchase.razorpay_payment_id)
            for event_id in ("evt_1", "evt_1", "evt_2"):
                response = self.webhook(self.event(purchase, payment_id=purchase.razorpay_payment_id), event_id=event_id)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_an_active_lower_membership_is_not_replaced(self):
        subscribe(self.user, self.LOWER)
        response = self.client.post(PURCHASES, {"package": self.PLAN}, format="json")
        self.assertEqual((response.status_code, response.json()["code"]), (409, "membership_active"))
        self.assertEqual(entitlements_for(self.user).package.code, self.LOWER)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)


class GoldValidityTests(TestCase):
    def test_six_calendar_months_in_india_time(self):
        cases = [
            (datetime(2026, 10, 27, 10, 0, tzinfo=IST), datetime(2027, 4, 27, 10, 0, tzinfo=IST)),
            (datetime(2026, 8, 31, 10, 0, tzinfo=IST), datetime(2027, 2, 28, 10, 0, tzinfo=IST)),
            (datetime(2027, 8, 31, 10, 0, tzinfo=IST), datetime(2028, 2, 29, 10, 0, tzinfo=IST)),  # leap year
            (datetime(2026, 12, 31, 23, 59, tzinfo=IST), datetime(2027, 6, 30, 23, 59, tzinfo=IST)),
            # 00:30 on 1 September in India is 31 August in UTC: the Indian date counts.
            (datetime(2026, 8, 31, 19, 0, tzinfo=dt_timezone.utc), datetime(2027, 3, 1, 0, 30, tzinfo=IST)),
        ]
        for start, end in cases:
            with self.subTest(start=start):
                self.assertEqual(add_months(start, 6), end)
        start = datetime(2026, 10, 27, 10, 0, tzinfo=IST)
        self.assertNotEqual((start + timedelta(days=180)).date(), add_months(start, 6).date())  # not 180 days

    def test_activated_gold_uses_its_six_months(self):
        subscription = subscribe(make_user(), "gold", starts_at=datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        self.assertEqual(subscription.ends_at, datetime(2027, 2, 28, 10, 0, tzinfo=IST))

    def test_expired_or_cancelled_gold_grants_nothing(self):
        for change in ({"ends_at": timezone.now() - timedelta(seconds=1)}, {"status": "cancelled"}):
            with self.subTest(change=change):
                user = make_user()
                subscription = subscribe(user, "gold")
                Subscription.objects.filter(pk=subscription.pk).update(**change)
                entitlements = client_for(user).get(ME).json()["entitlements"]
                self.assertEqual(entitlements["package_code"], "free")
                self.assertFalse(any(entitlements["features"][f] for f in FEATURE_PACKAGES))
                self.assertIsNone(entitlements["contact_view_limit"])


class PackageTermsTests(TestCase):
    """One authoritative Gold configuration, and every other package unchanged."""

    TERMS = {
        # code: (fee, validity months, contact limit, interest limit)
        "free": (Decimal("0"), None, None, 15),
        "silver": (Decimal("5000"), 3, 40, None),
        "gold": (Decimal("8000"), 6, 100, None),
        "diamond": (Decimal("12000"), 12, 100, None),
        "platinum": (Decimal("20000"), 3, None, None),
        "royal": (Decimal("100000"), 12, None, None),
    }

    def test_package_rows(self):
        for code, terms in self.TERMS.items():
            with self.subTest(package=code):
                package = MembershipPackage.objects.get(code=code)
                actual = (package.fee, package.validity_months, package.contact_view_limit, package.outgoing_interest_limit)
                self.assertEqual(actual, terms)
        gold = client_for().get("/api/v1/memberships/packages/").json()
        gold = next(item for item in gold if item["code"] == "gold")
        self.assertEqual((gold["contact_view_limit"], gold["validity_months"]), (100, 6))
        self.assertTrue(any("100 member contact numbers" in item["title"] for item in gold["benefits"]))
        self.assertFalse(any("70" in item["title"] for item in gold["benefits"]))

    def test_features_per_package(self):
        gold_only = {Feature.PRIORITY_VISIBILITY, Feature.MATCHMAKING_ASSISTANCE}
        expected = {
            "silver": GOLD_FEATURES - gold_only,
            "gold": GOLD_FEATURES,
            "diamond": GOLD_FEATURES,
            "platinum": {Feature.PHOTO_VIEWING},
            "royal": {Feature.PHOTO_VIEWING},
        }
        for code, features in expected.items():
            with self.subTest(package=code):
                user = make_user()
                subscribe(user, code)
                granted = {f for f in FEATURE_PACKAGES if entitlements_for(user).has(f)}
                self.assertEqual(granted, features)
        self.assertFalse(any(entitlements_for(make_user()).has(f) for f in FEATURE_PACKAGES))  # Free

    def test_paid_flag_on_the_account_or_a_pending_subscription_grants_nothing(self):
        user = make_user()
        Subscription.objects.create(user=user, plan_code="gold")  # recorded, never activated
        self.assertTrue(entitlements_for(user).is_free)
        response = client_for(user).get(ME, HTTP_X_MEMBERSHIP="gold")
        self.assertEqual(response.json()["entitlements"]["package_code"], "free")

    @override_settings(PRIORITY_VISIBILITY_ENABLED=False, MATCHMAKING_ASSISTANCE_AVAILABLE=False)
    def test_switched_off_benefits_are_reported_unavailable(self):
        user = make_user()
        subscribe(user, "gold")
        entitlements = client_for(user).get(ME).json()["entitlements"]
        self.assertEqual(entitlements["unavailable"], ["matchmaking_assistance", "priority_visibility"])
        self.assertTrue(entitlements["features"]["priority_visibility"])  # still part of the package
        silver = make_user()
        subscribe(silver, "silver")
        self.assertEqual(client_for(silver).get(ME).json()["entitlements"]["unavailable"], [])

    def test_dashboard_shows_what_the_backend_decided(self):
        user = make_user()
        make_profile(user, gender="male")
        subscribe(user, "gold")
        client = client_for(user)
        summary = client.get("/api/v1/dashboard/summary/").json()
        self.assertEqual(summary["entitlements"], client.get(ME).json()["entitlements"])
        self.assertEqual(summary["membership"]["plan_code"], "gold")
        self.assertEqual(summary["entitlements"]["contact_views_remaining"], 100)


class AssistanceTests(TestCase):
    """Run again for Diamond by DiamondAssistanceTests (tests_diamond.py)."""

    PLAN = "gold"

    def setUp(self):
        self.member = make_profile(gender="male")
        self.subscription = subscribe(self.member.user, self.PLAN)
        self.client = client_for(self.member.user)
        self.staff = make_staff("assign", first_name="Lakshmi", email="matchmaker@example.com")

    def ask(self, client=None, note="Looking for a teacher in Thrissur."):
        return (client or self.client).post(ASSISTANCE, {"note": note}, format="json")

    def test_request_assign_progress_complete(self):
        response = self.ask()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual((body["status"], body["assigned"], body["matchmaker_name"]), ("requested", False, None))
        item = AssistanceRequest.objects.get()
        self.assertEqual((item.user, item.subscription), (self.member.user, self.subscription))

        assistance.staff_update(item, self.staff, status=AssistanceStatus.REQUESTED, assigned_to=self.staff)
        mine = self.client.get(ASSISTANCE).json()["requests"][0]
        self.assertEqual((mine["status"], mine["assigned"], mine["matchmaker_name"]), ("assigned", True, "Lakshmi"))
        assistance.staff_update(item, self.staff, status=AssistanceStatus.IN_PROGRESS, assigned_to=self.staff)
        assistance.staff_update(item, self.staff, status=AssistanceStatus.COMPLETED, assigned_to=self.staff)

        item.refresh_from_db()
        self.assertIsNotNone(item.closed_at)
        self.assertEqual(
            list(AssistanceEvent.objects.values_list("status", flat=True)),
            ["requested", "assigned", "in_progress", "completed"],
        )
        self.assertEqual(Notification.objects.filter(recipient=self.member.user, kind="assistance_updated").count(), 3)
        with self.assertRaises(ValueError):  # closed requests stay closed
            assistance.staff_update(item, self.staff, status=AssistanceStatus.IN_PROGRESS, assigned_to=self.staff)
        self.assertEqual(self.ask().status_code, 201)  # and the member may ask again

    def test_no_assignment_without_a_staff_member(self):
        self.ask()
        item = AssistanceRequest.objects.get()
        for status in (AssistanceStatus.ASSIGNED, AssistanceStatus.IN_PROGRESS, AssistanceStatus.COMPLETED):
            with self.assertRaises(ValueError):
                assistance.staff_update(item, self.staff, status=status)
        with self.assertRaises(ValueError):
            assistance.staff_update(item, self.staff, status=AssistanceStatus.ASSIGNED, assigned_to=make_user())
        unavailable = assistance.staff_update(
            item, self.staff, status=AssistanceStatus.UNAVAILABLE, member_message="No matchmaker covers your area yet."
        )
        self.assertTrue(unavailable)
        mine = self.client.get(ASSISTANCE).json()["requests"][0]
        self.assertEqual((mine["status"], mine["assigned"], mine["message"]),
                         ("unavailable", False, "No matchmaker covers your area yet."))

    def test_one_open_request_and_only_eligible_members(self):
        self.assertEqual(self.ask().status_code, 201)
        again = self.ask()
        self.assertEqual((again.status_code, again.json()["code"]), (409, "already_requested"))

        for code in (None, "silver", "platinum"):
            with self.subTest(package=code):
                other = make_profile(gender="female")
                if code:
                    subscribe(other.user, code)
                response = self.ask(client_for(other.user))
                self.assertEqual((response.status_code, response.json()["code"]), (403, "upgrade_required"))
        expired = make_profile(gender="female")
        subscription = subscribe(expired.user, self.PLAN)
        Subscription.objects.filter(pk=subscription.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.ask(client_for(expired.user)).json()["code"], "upgrade_required")

        pending = make_profile(gender="female", status=ProfileStatus.PENDING_REVIEW)
        subscribe(pending.user, self.PLAN)
        self.assertEqual(self.ask(client_for(pending.user)).json()["code"], "profile_not_active")
        self.assertEqual(AssistanceRequest.objects.count(), 1)

    @override_settings(MATCHMAKING_ASSISTANCE_AVAILABLE=False)
    def test_unavailable_service_takes_no_requests(self):
        response = self.ask()
        self.assertEqual((response.status_code, response.json()["code"]), (403, "service_unavailable"))
        data = self.client.get(ASSISTANCE).json()
        self.assertEqual((data["included"], data["available"], data["requests"]), (True, False, []))

    def test_members_see_only_their_own_requests_and_no_staff_details(self):
        self.ask()
        item = AssistanceRequest.objects.get()
        item.staff_note = "Internal: prefers calls after 6pm."
        item.save()
        assistance.staff_update(item, self.staff, status=AssistanceStatus.ASSIGNED, assigned_to=self.staff)
        other = make_profile(gender="female")
        subscribe(other.user, self.PLAN)
        self.assertEqual(client_for(other.user).get(ASSISTANCE).json()["requests"], [])
        mine = self.client.get(ASSISTANCE).content.decode()
        for private in ("Internal", "matchmaker@example.com", self.staff.phone_number):
            self.assertNotIn(private, mine)
        self.assertEqual(client_for().get(ASSISTANCE).status_code, 401)
        self.assertIn("assistance", self.client.get(ME).json())

    def test_admin_changes_go_through_the_service(self):
        self.ask()
        item = AssistanceRequest.objects.get()
        admin = site._registry[AssistanceRequest]
        request = RequestFactory().post("/")
        request.user = make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        request._messages = type("M", (), {"add": lambda *a, **k: None})()
        admin.assign_to_me(request, AssistanceRequest.objects.all())
        item.refresh_from_db()
        self.assertEqual((item.status, item.assigned_to), (AssistanceStatus.ASSIGNED, request.user))
        self.assertEqual(AssistanceEvent.objects.filter(request=item).count(), 2)

    def test_admin_change_form_records_history_and_rejects_bad_changes(self):
        from django.test import Client
        from django.urls import reverse

        self.ask()
        item = AssistanceRequest.objects.get()
        superuser = make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        browser = Client()
        browser.force_login(superuser)
        url = reverse("admin:memberships_assistancerequest_change", args=[item.pk])
        self.assertEqual(browser.get(url).status_code, 200)
        form = {
            "status": "in_progress", "assigned_to": "", "member_message": "", "staff_note": "",
            **inline_management(item),
        }
        response = browser.post(url, form)
        self.assertEqual(response.status_code, 200)  # redisplayed with the error: no one assigned
        item.refresh_from_db()
        self.assertEqual(item.status, "requested")

        response = browser.post(url, {**form, "assigned_to": str(self.staff.pk), "staff_note": "Called on Monday."})
        self.assertEqual(response.status_code, 302, response.content[:500])
        item.refresh_from_db()
        self.assertEqual((item.status, item.assigned_to, item.staff_note), ("in_progress", self.staff, "Called on Monday."))
        self.assertEqual(list(item.events.values_list("status", flat=True)), ["requested", "in_progress"])
        self.assertEqual(self.client.get(ASSISTANCE).json()["requests"][0]["matchmaker_name"], "Lakshmi")
