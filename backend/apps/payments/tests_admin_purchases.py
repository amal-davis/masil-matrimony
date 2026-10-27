"""
Membership Purchases in the admin: access and permissions, the list and detail
pages, search and filters, CSV export, the summary figures, refunds as Razorpay
reports them, payment history, and that nothing in the admin can mark a
purchase paid. Razorpay is mocked (FakeRazorpay); no real payments.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.memberships.models import AssistanceRequest, Subscription, SubscriptionStatus
from apps.profiles.test_utils import make_profile, make_user

from . import reporting
from .models import Purchase, PurchaseEvent, PurchaseStatus, RefundStatus
from .tests import PURCHASES, PaymentsTestCase

LIST = reverse("admin:payments_purchase_changelist")
SUMMARY = reverse("admin:payments_purchase_summary")


def staff(*codenames):
    user = make_user(Role.ADMIN, is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="payments", codename__in=codenames))
    return type(user).objects.get(pk=user.pk)


class PurchaseAdminTestCase(PaymentsTestCase):
    def buy(self, package="silver", status="captured", user=None, **payment):
        """A purchase by `user` (a new member by default), paid or not through the mocked Razorpay."""
        user = user or make_user(first_name="Meera", last_name="Nair", email=f"m{Purchase.objects.count()}@example.com")
        if not hasattr(user, "profile"):
            make_profile(user, gender="female")
        client = Client()
        client.force_login(user)
        from rest_framework.test import APIClient

        api = APIClient()
        api.force_authenticate(user)
        response = api.post(PURCHASES, {"package": package}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        purchase = Purchase.objects.get(reference=response.json()["purchase"]["reference"])
        if status:
            payment_id = self.razorpay.pay(purchase.razorpay_order_id, status=status, **payment)
            with self.captureOnCommitCallbacks(execute=True):
                self.callback(purchase, payment_id, client=api)
        purchase.refresh_from_db()
        return purchase

    def browser(self, user):
        client = Client()
        client.force_login(user)
        return client

    def setUp(self):
        super().setUp()
        self.gst = self.settings(MEMBERSHIP_GST_RATE_PERCENT="18")
        self.gst.enable()
        self.addCleanup(self.gst.disable)
        self.superuser = make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.admin = self.browser(self.superuser)


class AccessTests(PurchaseAdminTestCase):
    def test_only_staff_with_permission_see_purchases_and_figures(self):
        self.buy()
        self.assertEqual(Client().get(LIST).status_code, 302)  # sign-in page
        member = self.browser(self.user)
        self.assertNotEqual(member.get(LIST).status_code, 200)
        no_perm = self.browser(staff())
        self.assertEqual(no_perm.get(LIST).status_code, 403)
        self.assertEqual(no_perm.get(SUMMARY).status_code, 403)

        viewer = self.browser(staff("view_purchase"))
        listing = viewer.get(LIST)
        self.assertEqual(listing.status_code, 200)
        self.assertNotContains(listing, "₹5,900.00")  # amounts need the financial permission
        summary = viewer.get(SUMMARY)
        self.assertEqual(summary.context["figures"]["paid"], 1)
        self.assertNotContains(summary, "Gross collected")

        finance = self.browser(staff("view_purchase", "view_purchase_financials"))
        self.assertContains(finance.get(LIST), "₹5,900.00")
        self.assertContains(finance.get(SUMMARY), "Gross collected")

    def test_sidebar_has_its_own_section(self):
        from apps.core.admin_site import sidebar_navigation
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.user = self.superuser
        sections = {section["title"]: [item["title"] for item in section["items"]] for section in sidebar_navigation(request)}
        self.assertEqual(sections["Membership Purchases"], ["Summary", "Purchases", "Receipts", "Razorpay webhooks"])
        self.assertNotIn("Online purchases", sections["Memberships"])


class ListAndDetailTests(PurchaseAdminTestCase):
    def test_paid_pending_and_failed_purchases_with_their_membership(self):
        paid = self.buy("silver")
        pending = self.buy("gold", status=None)
        failed = self.buy("diamond", status="failed", error_description="Card declined")
        rows = {p.pk: p for p in self.admin.get(LIST).context["cl"].result_list}
        self.assertEqual(set(rows), {paid.pk, pending.pk, failed.pk})
        states = {pk: reporting.membership_state(p)[1] for pk, p in rows.items()}
        self.assertEqual(states, {paid.pk: "Active", pending.pk: "Pending payment", failed.pk: "Payment failed"})

        Subscription.objects.filter(pk=paid.subscription_id).update(ends_at=timezone.now() - timedelta(seconds=1))
        paid.refresh_from_db()
        self.assertEqual(reporting.membership_state(paid), ("expired", "Expired"))
        self.assertEqual(paid.status, PurchaseStatus.PAID)  # payment status stays apart from membership status

    def test_detail_page_links_records_and_shows_no_secrets(self):
        purchase = self.buy("silver")
        page = self.admin.get(reverse("admin:payments_purchase_change", args=[purchase.pk]))
        self.assertEqual(page.status_code, 200)
        text = page.content.decode()
        for expected in (purchase.razorpay_order_id, purchase.razorpay_payment_id, "Payment status history",
                         reverse("admin:memberships_subscription_change", args=[purchase.subscription_id]),
                         reverse("admin:profiles_profile_change", args=[purchase.user.profile.pk])):
            self.assertIn(expected, text)
        for secret in (settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET):
            self.assertNotIn(secret, text)

    def test_platinum_purchase_links_its_service_case(self):
        purchase = self.buy("platinum")
        case = AssistanceRequest.objects.get(subscription=purchase.subscription)
        page = self.admin.get(reverse("admin:payments_purchase_change", args=[purchase.pk]))
        self.assertContains(page, reverse("admin:memberships_assistancerequest_change", args=[case.pk]))
        self.assertContains(page, "Awaiting assignment")
        self.assertContains(page, "not assigned")

    def test_admin_cannot_edit_or_mark_paid(self):
        purchase = self.buy("silver", status=None)
        url = reverse("admin:payments_purchase_change", args=[purchase.pk])
        self.admin.post(url, {"status": "paid", "razorpay_payment_id": "pay_FAKE", "total_amount": "1.00"})
        purchase.refresh_from_db()
        self.assertEqual((purchase.status, purchase.razorpay_payment_id, purchase.total_amount),
                         (PurchaseStatus.AWAITING_PAYMENT, None, Decimal("5900.00")))
        self.assertFalse(Subscription.objects.filter(user=purchase.user).exists())
        self.assertEqual(self.admin.get(reverse("admin:payments_purchase_add")).status_code, 403)
        self.assertEqual(self.admin.post(reverse("admin:payments_purchase_delete", args=[purchase.pk])).status_code, 403)

    def test_list_queries_dont_grow_with_rows(self):
        def queries():
            with CaptureQueriesContext(connection) as context:
                self.assertEqual(self.admin.get(LIST).status_code, 200)
            return len(context.captured_queries)

        self.buy("silver")
        few = queries()
        for package in ("gold", "diamond", "silver", "gold"):
            self.buy(package)
        self.assertEqual(queries(), few)


class SearchFilterTests(PurchaseAdminTestCase):
    def found(self, **params):
        return [p.reference for p in self.admin.get(LIST, params).context["cl"].result_list]

    def test_search_by_every_identifier(self):
        purchase = self.buy("silver")
        other = self.buy("gold")
        user = purchase.user
        for query in ("Meera", user.profile.profile_code, user.phone_number, user.email, purchase.reference,
                      purchase.razorpay_order_id, purchase.razorpay_payment_id):
            with self.subTest(query=query):
                self.assertIn(purchase.reference, self.found(q=query))
        self.assertEqual(self.found(q=purchase.razorpay_payment_id), [purchase.reference])
        self.assertNotIn(purchase.reference, self.found(q=other.reference))

    def test_filters(self):
        paid = self.buy("silver")
        pending = self.buy("gold", status=None)
        expired = self.buy("diamond")
        Subscription.objects.filter(pk=expired.subscription_id).update(ends_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.found(package_code="gold"), [pending.reference])
        self.assertEqual(sorted(self.found(status__exact="paid")), sorted([paid.reference, expired.reference]))
        self.assertEqual(self.found(membership="expired"), [expired.reference])
        self.assertEqual(self.found(membership="active"), [paid.reference])
        self.assertEqual(self.found(membership="pending_payment"), [pending.reference])
        self.assertEqual(self.found(refund_status__exact="none", status__exact="paid").__len__(), 2)
        today = timezone.localdate()
        self.assertEqual(len(self.found(**{"created_at__gte": f"{today}", "created_at__lt": f"{today + timedelta(days=1)}"})), 3)


class ExportTests(PurchaseAdminTestCase):
    def export(self, client, ids):
        return client.post(LIST, {"action": "export_csv", "_selected_action": ids})

    def test_export_needs_permission_and_contains_only_business_data(self):
        purchase = self.buy("silver")
        Purchase.objects.filter(pk=purchase.pk).update(billing_name="=HYPERLINK(\"http://x\")")
        viewer = self.browser(staff("view_purchase", "change_purchase"))
        response = self.export(viewer, [purchase.pk])
        self.assertNotEqual(response.get("Content-Type", ""), "text/csv; charset=utf-8")

        exporter = self.browser(staff("view_purchase", "change_purchase", "export_purchase"))
        csv_text = self.export(exporter, [purchase.pk]).content.decode()
        self.assertIn(purchase.reference, csv_text)
        self.assertIn("'=HYPERLINK", csv_text)  # can't run as a formula
        for private in (purchase.user.phone_number, purchase.user.email, settings.RAZORPAY_KEY_SECRET):
            self.assertNotIn(private, csv_text)
        self.assertNotIn("5900.00", csv_text)  # amounts need the financial permission

        finance = self.browser(staff("view_purchase", "change_purchase", "export_purchase", "view_purchase_financials"))
        self.assertIn("5900.00", self.export(finance, [purchase.pk]).content.decode())


class SummaryAndRefundTests(PurchaseAdminTestCase):
    def test_summary_figures(self):
        silver = self.buy("silver")  # 5900
        gold = self.buy("gold")  # 9440
        expired = self.buy("diamond")  # 14160
        cancelled = self.buy("silver")
        self.buy("gold", status=None)  # pending
        self.buy("silver", status="authorized")  # pending: authorised, not captured
        self.buy("diamond", status="failed")
        test_mode = self.buy("silver")
        Purchase.objects.exclude(pk=test_mode.pk).update(mode="live")
        Subscription.objects.filter(pk=expired.subscription_id).update(ends_at=timezone.now() - timedelta(days=1))
        Subscription.objects.filter(pk=cancelled.subscription_id).update(status=SubscriptionStatus.CANCELLED)
        Purchase.objects.filter(pk=gold.pk).update(paid_at=timezone.now() - timedelta(days=62))  # an earlier month

        figures = reporting.summary()
        self.assertEqual(
            {key: figures[key] for key in ("total", "paid", "active", "expired", "cancelled", "pending", "failed",
                                           "refunded", "test_paid")},
            # Memberships count whatever the mode; only revenue leaves test mode out.
            {"total": 8, "paid": 5, "active": 3, "expired": 1, "cancelled": 1, "pending": 2, "failed": 1,
             "refunded": 0, "test_paid": 1},
        )
        self.assertEqual(figures["gross"], Decimal("35400.00"))  # 5900 + 9440 + 14160 + 5900, live only
        self.assertEqual(figures["gross_month"], Decimal("25960.00"))
        self.assertEqual(figures["net"], figures["gross"])
        self.assertEqual(self.admin.get(SUMMARY).context["figures"]["gross"], Decimal("35400.00"))
        self.assertIsNotNone(silver.subscription)

    def test_duplicate_webhooks_count_once(self):
        purchase = self.buy("silver")
        Purchase.objects.update(mode="live")
        with self.captureOnCommitCallbacks(execute=True):
            for event_id in ("evt_1", "evt_1", "evt_2", "evt_2"):
                self.webhook(self.event(purchase, payment_id=purchase.razorpay_payment_id), event_id=event_id)
        figures = reporting.summary()
        self.assertEqual((figures["total"], figures["paid"], figures["gross"]), (1, 1, Decimal("5900.00")))
        self.assertEqual(Subscription.objects.filter(user=purchase.user).count(), 1)
        self.assertEqual(PurchaseEvent.objects.filter(purchase=purchase, status="paid").count(), 1)

    def test_refunds_are_recorded_from_razorpay_and_leave_the_membership_to_staff(self):
        purchase = self.buy("silver")
        Purchase.objects.update(mode="live")
        payment = next(p for p in self.razorpay.payments[purchase.razorpay_order_id] if p["id"] == purchase.razorpay_payment_id)
        payment.update(amount_refunded=100000, refund_status="partial")
        refund = self.event(purchase, name="refund.processed", payment_id=purchase.razorpay_payment_id)
        self.assertEqual(self.webhook(refund, event_id="evt_r1").status_code, 200)
        purchase.refresh_from_db()
        self.assertEqual((purchase.refund_status, purchase.refunded_amount_subunits), (RefundStatus.PARTIAL, 100000))

        payment.update(status="refunded", amount_refunded=purchase.amount_subunits, refund_status="full")
        self.webhook(self.event(purchase, name="payment.refunded", payment_id=purchase.razorpay_payment_id), event_id="evt_r2")
        purchase.refresh_from_db()
        self.assertEqual(purchase.refund_status, RefundStatus.FULL)
        self.assertEqual(purchase.status, PurchaseStatus.PAID)  # it was paid; the refund is recorded beside it
        self.assertTrue(purchase.subscription.is_current)  # not revoked automatically
        history = list(purchase.events.values_list("status", "refund_status", "source"))
        self.assertEqual(history[-2:], [("paid", "partial", "webhook"), ("paid", "full", "webhook")])
        figures = reporting.summary()
        self.assertEqual((figures["refunded"], figures["refunded_amount"], figures["net"]),
                         (1, Decimal("5900.00"), Decimal("0.00")))
        page = self.admin.get(reverse("admin:payments_purchase_change", args=[purchase.pk]))
        self.assertContains(page, "Fully refunded")

    def test_staff_status_check_is_recorded_with_who_ran_it(self):
        purchase = self.buy("gold", status=None)
        self.razorpay.pay(purchase.razorpay_order_id)
        with self.captureOnCommitCallbacks(execute=True):
            self.admin.post(LIST, {"action": "check_with_razorpay", "_selected_action": [purchase.pk]})
        event = purchase.events.last()
        self.assertEqual((event.status, event.source, event.staff), ("paid", "staff_check", self.superuser))
        self.assertEqual(list(purchase.events.values_list("source", flat=True)), ["order", "staff_check"])
