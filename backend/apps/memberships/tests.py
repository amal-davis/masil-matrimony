import json
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.profiles.test_utils import client_for, make_user

from .entitlements import entitlements_for
from .models import MembershipPackage, Subscription, SubscriptionStatus, TaxTreatment, add_months
from .plans import PackageCode, PlanCode

URL = "/api/v1/memberships/me/"
PACKAGES_URL = "/api/v1/memberships/packages/"


def subscribe(user, code, starts_at=None):
    subscription = Subscription.objects.create(user=user, plan_code=code)
    subscription.activate(starts_at=starts_at)
    subscription.save()
    return subscription


class AddMonthsTests(TestCase):
    def test_add_months(self):
        start = datetime(2026, 1, 31, 10, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(add_months(start, 1), datetime(2026, 2, 28, 10, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(add_months(start, 12), datetime(2027, 1, 31, 10, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(add_months(datetime(2026, 11, 15, tzinfo=dt_timezone.utc), 3).month, 2)


class PackageCatalogueTests(TestCase):
    """The six packages seeded by migration 0003 and served by the public API."""

    def test_six_packages_in_order(self):
        body = client_for().get(PACKAGES_URL).json()
        self.assertEqual([item["code"] for item in body], ["free", "silver", "gold", "diamond", "platinum", "royal"])

    def test_fees_tax_validity_and_limits(self):
        packages = {item["code"]: item for item in client_for().get(PACKAGES_URL).json()}
        expected = {
            # code: (fee, tax treatment, validity months, contact limit, interest limit)
            "free": ("0.00", "no_fee", None, None, 15),
            "silver": ("5000.00", "gst_extra", 3, 40, None),
            "gold": ("8000.00", "gst_extra", 6, 100, None),
            "diamond": ("12000.00", "gst_extra", 12, 100, None),
            "platinum": ("20000.00", "gst_extra", 3, None, None),
            "royal": ("100000.00", "gst_stated", 12, None, None),
        }
        for code, (fee, tax, validity, contacts, interests) in expected.items():
            with self.subTest(package=code):
                item = packages[code]
                self.assertEqual(item["fee"], fee)
                self.assertEqual(item["tax_treatment"], tax)
                self.assertEqual(item["validity_months"], validity)
                self.assertEqual(item["contact_view_limit"], contacts)
                self.assertEqual(item["outgoing_interest_limit"], interests)
                self.assertTrue(item["benefits"])

    def test_gst_is_not_calculated_without_a_configured_rate(self):
        packages = {item["code"]: item for item in client_for().get(PACKAGES_URL).json()}
        for code in ("silver", "gold", "diamond", "platinum"):
            with self.subTest(package=code):
                self.assertIsNone(packages[code]["gst_amount"])
                self.assertIsNone(packages[code]["total_payable"])
                self.assertIsNone(packages[code]["stated_gst_rate"])
        self.assertEqual(packages["free"]["total_payable"], "0.00")

    def test_royal_keeps_its_stated_gst(self):
        royal = next(item for item in client_for().get(PACKAGES_URL).json() if item["code"] == "royal")
        self.assertEqual(royal["stated_gst_rate"], "18.00")
        self.assertEqual(royal["gst_amount"], "18000.00")
        self.assertEqual(royal["total_payable"], "118000.00")
        self.assertEqual(royal["fee_label"], "Annual service fee")

    def test_gold_contact_limit_is_the_confirmed_value(self):
        gold = MembershipPackage.objects.get(code=PackageCode.GOLD)
        self.assertEqual(gold.contact_view_limit, 100)
        self.assertTrue(any("up to 100 member contact numbers" in item["title"] for item in gold.benefits))
        self.assertFalse(any("70" in item["title"] for item in gold.benefits))

    def test_frontend_preview_snapshot_matches_the_api(self):
        # The static UI preview can't call the API, so it shows this snapshot. Regenerate it after
        # changing the seeded packages, so the preview never shows prices the backend doesn't.
        snapshot = Path(settings.BASE_DIR).parent / "frontend/features/packages/preview-packages.json"
        if not snapshot.exists():
            self.skipTest("frontend checkout not present")
        self.assertEqual(client_for().get(PACKAGES_URL).json(), json.loads(snapshot.read_text(encoding="utf-8")))

    def test_unavailable_packages_are_hidden(self):
        MembershipPackage.objects.filter(code=PackageCode.SILVER).update(is_available=False)
        codes = [item["code"] for item in client_for().get(PACKAGES_URL).json()]
        self.assertNotIn("silver", codes)
        self.assertIn("diamond", codes)

    def test_existing_packages_kept(self):
        for code in ("diamond", "platinum", "royal"):
            self.assertTrue(MembershipPackage.objects.filter(code=code, is_available=True).exists())

    def test_validation(self):
        free = MembershipPackage.objects.get(code=PackageCode.FREE)
        free.validity_months = 6
        with self.assertRaises(ValidationError):
            free.full_clean()

        silver = MembershipPackage.objects.get(code=PackageCode.SILVER)
        silver.outgoing_interest_limit = 10
        with self.assertRaises(ValidationError):
            silver.full_clean()

        royal = MembershipPackage.objects.get(code=PackageCode.ROYAL)
        royal.stated_gst_rate = None
        with self.assertRaises(ValidationError):
            royal.full_clean()

        diamond = MembershipPackage.objects.get(code=PackageCode.DIAMOND)
        diamond.benefits = ["not an object"]
        with self.assertRaises(ValidationError):
            diamond.full_clean()
        diamond.benefits = [{"title": "Advanced Search"}]
        diamond.full_clean()


class MembershipApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = client_for(self.user)

    def test_no_subscription_is_free(self):
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"], [])
        self.assertIs(body["online_payment_available"], False)
        self.assertEqual(body["entitlements"]["package_code"], "free")
        self.assertEqual(body["entitlements"]["outgoing_interest_limit"], 15)
        self.assertEqual(body["entitlements"]["outgoing_interests_used"], 0)
        self.assertIsNone(body["entitlements"]["contact_view_limit"])

    def test_requires_member(self):
        self.assertEqual(client_for().get(URL).status_code, 401)

    def test_pending_subscription_grants_nothing(self):
        Subscription.objects.create(user=self.user, plan_code=PlanCode.DIAMOND)
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["entitlements"]["package_code"], "free")
        self.assertEqual(len(body["history"]), 1)
        self.assertEqual(body["history"][0]["status"], "pending")
        self.assertIsNone(body["history"][0]["ends_at"])

    def test_activation_sets_validity_period(self):
        expected = {"silver": 3, "gold": 6, "diamond": 12, "platinum": 3, "royal": 12}
        for code, months in expected.items():
            with self.subTest(plan=code):
                start = timezone.now()
                subscription = subscribe(self.user, code, starts_at=start)
                self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
                self.assertEqual(subscription.validity_months, months)
                self.assertEqual(subscription.ends_at, add_months(start, months))
                self.assertTrue(subscription.is_current)

    def test_current_subscription(self):
        subscribe(self.user, PlanCode.SILVER)
        body = self.client.get(URL).json()
        current = body["current"]
        self.assertEqual(current["plan_code"], "silver")
        self.assertEqual(current["status"], "active")
        self.assertEqual(current["package_fee"], "5000.00")
        self.assertEqual(current["contact_view_limit"], 40)
        self.assertEqual(current["contact_views_used"], 0)
        self.assertEqual(body["entitlements"]["package_code"], "silver")
        self.assertIsNone(body["entitlements"]["outgoing_interest_limit"])
        self.assertEqual(body["entitlements"]["contact_view_limit"], 40)

    def test_subscription_keeps_terms_when_package_changes(self):
        subscription = subscribe(self.user, PlanCode.DIAMOND)
        MembershipPackage.objects.filter(code=PackageCode.DIAMOND).update(
            fee=Decimal("15000"), validity_months=6, contact_view_limit=50
        )
        subscription.refresh_from_db()
        self.assertEqual(subscription.package_fee, Decimal("12000.00"))
        self.assertEqual(subscription.validity_months, 12)
        self.assertEqual(subscription.contact_view_limit, 100)
        self.assertEqual(entitlements_for(self.user).contact_view_limit, 100)

    def test_expired_subscription_loses_paid_entitlements(self):
        subscribe(self.user, PlanCode.GOLD, starts_at=timezone.now() - timedelta(days=200))
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"][0]["status"], "expired")
        self.assertEqual(body["entitlements"]["package_code"], "free")
        self.assertIsNone(body["entitlements"]["contact_view_limit"])
        self.assertEqual(body["entitlements"]["outgoing_interest_limit"], 15)

    def test_cancelled_subscription(self):
        subscription = subscribe(self.user, PlanCode.ROYAL)
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.save()
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"][0]["status"], "cancelled")

    def test_only_own_subscriptions(self):
        subscribe(make_user(), PlanCode.DIAMOND)
        body = self.client.get(URL).json()
        self.assertIsNone(body["current"])
        self.assertEqual(body["history"], [])


class PackageAdminTests(TestCase):
    URL = "/admin/memberships/membershippackage/"

    def setUp(self):
        self.staff = make_user(role=Role.ADMIN, is_staff=True)
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="memberships",
                codename__in=["view_membershippackage", "change_membershippackage"],
            )
        )
        self.client.force_login(self.staff)
        self.gold = MembershipPackage.objects.get(code=PackageCode.GOLD)

    def change_url(self):
        return f"{self.URL}{self.gold.pk}/change/"

    def form_data(self, **overrides):
        data = {
            "category": "online", "is_available": "on", "display_order": 30,
            "name": "Gold Membership", "subtitle": "", "tagline": "", "service_label": "Online Membership",
            "description": "New description.", "benefits": '[{"title": "Advanced Search"}]',
            "terms_title": "Validity Terms", "terms_body": "Terms.", "cta_label": "Choose Gold",
            "fee_label": "Membership fee",
        }
        data.update(overrides)
        return data

    def test_list_and_change_page(self):
        self.assertEqual(self.client.get(self.URL).status_code, 200)
        self.assertEqual(self.client.get(self.change_url()).status_code, 200)

    def test_staff_without_terms_permission_cannot_change_fee(self):
        response = self.client.post(self.change_url(), self.form_data(fee="1", contact_view_limit="999"))
        self.assertEqual(response.status_code, 302)
        self.gold.refresh_from_db()
        self.assertEqual(self.gold.description, "New description.")
        self.assertEqual(self.gold.fee, Decimal("8000.00"))
        self.assertEqual(self.gold.contact_view_limit, 100)

    def test_terms_permission_allows_fee_change(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="change_package_terms"))
        data = self.form_data(
            fee="9000", tax_treatment="gst_extra", stated_gst_rate="", validity_months="6",
            contact_view_limit="100", outgoing_interest_limit="",
        )
        response = self.client.post(self.change_url(), data)
        self.assertEqual(response.status_code, 302)
        self.gold.refresh_from_db()
        self.assertEqual(self.gold.fee, Decimal("9000.00"))
        self.assertEqual(self.gold.tax_treatment, TaxTreatment.GST_EXTRA)

    def test_packages_cannot_be_added_or_deleted(self):
        self.staff.user_permissions.add(
            *Permission.objects.filter(codename__in=["add_membershippackage", "delete_membershippackage"])
        )
        self.assertEqual(self.client.get(f"{self.URL}add/").status_code, 403)
        self.assertEqual(self.client.get(f"{self.URL}{self.gold.pk}/delete/").status_code, 403)

    def test_member_cannot_open_admin(self):
        self.client.force_login(make_user())
        self.assertNotEqual(self.client.get(self.URL).status_code, 200)


class SubscriptionAdminTests(TestCase):
    URL = "/admin/memberships/subscription/"

    def setUp(self):
        self.staff = make_user(role=Role.ADMIN, is_staff=True)
        self.staff.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="memberships", codename__endswith="subscription")
        )
        self.client.force_login(self.staff)
        self.member = make_user()

    def test_record_copies_terms_and_activation_needs_the_action(self):
        response = self.client.post(f"{self.URL}add/", {"user": self.member.pk, "plan_code": "gold", "staff_note": ""})
        self.assertEqual(response.status_code, 302)
        subscription = Subscription.objects.get(user=self.member)
        self.assertEqual(subscription.status, SubscriptionStatus.PENDING)
        self.assertEqual(subscription.package_fee, Decimal("8000.00"))
        self.assertEqual(subscription.validity_months, 6)
        self.assertEqual(subscription.contact_view_limit, 100)
        self.assertIsNone(entitlements_for(self.member).subscription)

        self.client.post(self.URL, {"action": "activate", "_selected_action": [subscription.pk]})
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, 6))
        self.assertEqual(entitlements_for(self.member).package.code, "gold")

    def test_contact_views_used_is_read_only(self):
        subscription = subscribe(self.member, PlanCode.SILVER)
        self.client.post(
            f"{self.URL}{subscription.pk}/change/", {"contact_views_used": 0, "staff_note": "note"}
        )
        Subscription.objects.filter(pk=subscription.pk).update(contact_views_used=5)
        self.client.post(f"{self.URL}{subscription.pk}/change/", {"contact_views_used": 0, "staff_note": "x"})
        subscription.refresh_from_db()
        self.assertEqual(subscription.contact_views_used, 5)
        self.assertEqual(subscription.staff_note, "x")

    def test_unavailable_package_cannot_be_recorded(self):
        MembershipPackage.objects.filter(code=PackageCode.SILVER).update(is_available=False)
        response = self.client.post(f"{self.URL}add/", {"user": self.member.pk, "plan_code": "silver"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subscription.objects.filter(user=self.member).exists())


class ExistingDataMigrationTests(TransactionTestCase):
    """Subscriptions and interests recorded before the package catalogue survive the upgrade unchanged."""

    # Restore the seeded packages afterwards for any later test.
    serialized_rollback = True

    before = [("memberships", "0001_initial"), ("interactions", "0001_initial"), ("profiles", "0001_initial")]
    after = [("memberships", "0003_seed_packages_and_backfill_subscription_terms"),
             ("interactions", "0003_backfill_free_interest_limit")]

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_upgrade_preserves_and_backfills(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        User = old.get_model("accounts", "User")
        Old = old.get_model("memberships", "Subscription")
        now = timezone.now()
        user = User.objects.create(email="legacy@example.com", role="member")
        active = Old.objects.create(user=user, plan_code="diamond", status="active", starts_at=now - timedelta(days=10),
                                    ends_at=now + timedelta(days=300), contact_views_used=7, staff_note="paid cash")
        pending = Old.objects.create(user=user, plan_code="platinum", status="pending")

        executor = MigrationExecutor(connection)
        executor.migrate(self.after)
        new = executor.loader.project_state(self.after).apps
        New = new.get_model("memberships", "Subscription")
        active = New.objects.get(pk=active.pk)
        self.assertEqual((active.status, active.contact_views_used, active.staff_note), ("active", 7, "paid cash"))
        self.assertEqual((active.validity_months, active.contact_view_limit), (12, 100))
        self.assertIsNone(active.package_fee)  # what was paid offline was never recorded
        pending = New.objects.get(pk=pending.pk)
        self.assertEqual((pending.validity_months, pending.contact_view_limit), (3, None))
        self.assertEqual(pending.package_fee, Decimal("20000.00"))
        self.assertEqual(new.get_model("memberships", "MembershipPackage").objects.count(), 6)
