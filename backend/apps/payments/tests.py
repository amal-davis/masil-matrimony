"""
Razorpay membership checkout, payment confirmation, webhooks, receipts and
their emails. Razorpay is always mocked (no network); emails go to Django's
locmem outbox.
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.memberships.models import MembershipPackage, Subscription, SubscriptionStatus, add_months
from apps.memberships.plans import PackageCode
from apps.notifications.mail import EmailError
from apps.profiles.test_utils import client_for, make_profile, make_user

from . import razorpay_api, services
from .models import EmailStatus, Purchase, PurchaseStatus, Receipt, WebhookEvent
from .receipts import financial_year

PURCHASES = "/api/v1/payments/purchases/"
WEBHOOK = "/api/v1/payments/razorpay/webhook/"

ROYAL_TOTAL_PAISE = 118_000_00  # ₹1,00,000 + 18% stated GST


def sign(message: str, secret: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class FakeRazorpay:
    """Stands in for apps.payments.razorpay_api's network calls."""

    def __init__(self):
        self.orders = {}
        self.payments = {}  # order_id -> list of payment dicts
        self.create_calls = 0
        self.payment_count = 0
        self.fail_create = False
        self.fail_fetch = False

    def create_order(self, amount, currency, receipt, notes):
        self.create_calls += 1
        if self.fail_create:
            raise razorpay_api.RazorpayError("Razorpay answered HTTP 500 SERVER_ERROR: down")
        order_id = f"order_TEST{self.create_calls:010d}"
        self.orders[order_id] = {"id": order_id, "amount": amount, "currency": currency, "receipt": receipt, "notes": notes}
        return self.orders[order_id]

    def order_payments(self, order_id):
        if self.fail_fetch:
            raise razorpay_api.RazorpayError("Razorpay request failed: TimeoutError")
        return [dict(p) for p in self.payments.get(order_id, [])]

    def pay(self, order_id, status="captured", amount=None, currency="INR", payment_id=None, created_at=None, **extra):
        if payment_id is None:
            # Razorpay payment ids are unique across all orders.
            self.payment_count += 1
            payment_id = f"pay_TEST{self.payment_count:010d}"
        payment = {
            "id": payment_id, "entity": "payment", "order_id": order_id, "status": status,
            "amount": self.orders[order_id]["amount"] if amount is None else amount, "currency": currency,
            "method": "upi", "created_at": created_at or int(timezone.now().timestamp()), **extra,
        }
        existing = [p for p in self.payments.setdefault(order_id, []) if p["id"] != payment_id]
        self.payments[order_id] = existing + [payment]
        return payment_id


class PaymentsTestCase(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.razorpay = FakeRazorpay()
        patches = [
            mock.patch.object(razorpay_api, "create_order", self.razorpay.create_order),
            mock.patch.object(razorpay_api, "order_payments", self.razorpay.order_payments),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.user = make_user(first_name="Anu", last_name="Mohan", email="anu@example.com")
        make_profile(self.user, gender="female")
        self.client = client_for(self.user)

    def start(self, package="royal", client=None):
        return (client or self.client).post(PURCHASES, {"package": package}, format="json")

    def started(self, package="royal") -> Purchase:
        response = self.start(package)
        self.assertEqual(response.status_code, 201, response.content)
        return Purchase.objects.get(reference=response.json()["purchase"]["reference"])

    def callback(self, purchase, payment_id, signature=None, order_id=None, client=None):
        order_id = order_id or purchase.razorpay_order_id
        signature = signature or sign(f"{purchase.razorpay_order_id}|{payment_id}", settings.RAZORPAY_KEY_SECRET)
        return (client or self.client).post(
            f"{PURCHASES}{purchase.reference}/verify/",
            {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature},
            format="json",
        )

    def webhook(self, body: dict, event_id="evt_1", secret=None):
        raw = json.dumps(body).encode()
        return self.client.generic(
            "POST", WEBHOOK, raw, content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=sign(raw.decode(), secret or settings.RAZORPAY_WEBHOOK_SECRET),
            HTTP_X_RAZORPAY_EVENT_ID=event_id,
        )

    def event(self, purchase, name="payment.captured", payment_id="pay_X"):
        return {
            "entity": "event", "event": name, "contains": ["payment"],
            "payload": {"payment": {"entity": {"id": payment_id, "order_id": purchase.razorpay_order_id, "status": "captured",
                                               "amount": purchase.amount_subunits, "currency": "INR",
                                               "email": "anu@example.com", "contact": "+919800000000"}}},
        }


class PricingTests(PaymentsTestCase):
    def test_royal_uses_its_stated_gst_once(self):
        price = services.quote(MembershipPackage.objects.get(code="royal"))
        self.assertEqual((price.base, price.gst_rate, price.gst, price.total), (
            Decimal("100000.00"), Decimal("18.00"), Decimal("18000.00"), Decimal("118000.00")))
        self.assertEqual(price.amount_subunits, ROYAL_TOTAL_PAISE)

    def test_applicable_gst_packages_need_a_confirmed_rate(self):
        silver = MembershipPackage.objects.get(code="silver")
        with self.assertRaises(services.PriceNotConfirmed):
            services.quote(silver)
        response = self.start("silver")
        self.assertEqual((response.status_code, response.json()["code"]), (409, "price_not_confirmed"))
        self.assertEqual(self.razorpay.create_calls, 0)
        with override_settings(MEMBERSHIP_GST_RATE_PERCENT="18"):
            price = services.quote(silver)
            self.assertEqual((price.gst, price.total, price.amount_subunits), (Decimal("900.00"), Decimal("5900.00"), 590000))
            # Royal keeps its own stated rate whatever the setting says.
            self.assertEqual(services.quote(MembershipPackage.objects.get(code="royal")).total, Decimal("118000.00"))

    @override_settings(MEMBERSHIP_GST_RATE_PERCENT="12.345")
    def test_gst_is_rounded_half_up_to_the_paisa(self):
        price = services.quote(MembershipPackage.objects.get(code="silver"))
        self.assertEqual(price.gst, Decimal("617.25"))  # 5000 x 12.345% = 617.25
        self.assertEqual(price.amount_subunits, 561725)

    @override_settings(MEMBERSHIP_GST_RATE_PERCENT="abc")
    def test_an_invalid_rate_is_treated_as_unconfirmed(self):
        with self.assertRaises(services.PriceNotConfirmed):
            services.quote(MembershipPackage.objects.get(code="silver"))

    def test_free_and_unknown_packages_cant_be_bought(self):
        response = self.start("free")
        self.assertEqual((response.status_code, response.json()["code"]), (409, "not_purchasable"))
        for value in ("platinum-plus", "", None, 7):
            with self.subTest(package=value):
                self.assertEqual(self.start(value).status_code, 400)
        MembershipPackage.objects.filter(code="royal").update(is_available=False)
        self.assertEqual(self.start("royal").json()["code"], "package_not_found")
        self.assertFalse(Purchase.objects.exists())

    def test_the_browser_cant_set_the_amount(self):
        response = self.client.post(PURCHASES, {"package": "royal", "amount": 100, "currency": "USD"}, format="json")
        self.assertEqual(response.status_code, 201)
        purchase = Purchase.objects.get()
        self.assertEqual((purchase.amount_subunits, purchase.currency), (ROYAL_TOTAL_PAISE, "INR"))
        order = self.razorpay.orders[purchase.razorpay_order_id]
        self.assertEqual((order["amount"], order["currency"]), (ROYAL_TOTAL_PAISE, "INR"))

    def test_quote_endpoint_matches_the_order(self):
        body = self.client.get("/api/v1/payments/checkout/royal/").json()
        self.assertTrue(body["available"])
        self.assertEqual(body["price"], {"base": "100000.00", "gst_rate": "18.00", "gst": "18000.00",
                                         "total": "118000.00", "currency": "INR"})
        self.assertEqual(body["customer"]["email"], "anu@example.com")
        checkout = self.start().json()["checkout"]
        self.assertEqual(checkout["amount"], ROYAL_TOTAL_PAISE)
        blocked = self.client.get("/api/v1/payments/checkout/silver/").json()
        self.assertEqual((blocked["available"], blocked["price"], blocked["blocked"]["code"]), (False, None, "price_not_confirmed"))


class StartCheckoutTests(PaymentsTestCase):
    def test_creates_a_purchase_snapshot_and_a_razorpay_order(self):
        response = self.start()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.status, PurchaseStatus.AWAITING_PAYMENT)
        self.assertEqual((purchase.package_code, purchase.validity_months, purchase.billing_email),
                         ("royal", 12, "anu@example.com"))
        order = self.razorpay.orders[purchase.razorpay_order_id]
        self.assertEqual(order["receipt"], purchase.reference)
        self.assertLessEqual(len(purchase.reference), 40)
        self.assertNotIn("anu@example.com", json.dumps(order["notes"]))
        # Only what checkout needs, and no secret.
        self.assertEqual(body["checkout"]["key"], settings.RAZORPAY_KEY_ID)
        self.assertEqual(body["checkout"]["order_id"], purchase.razorpay_order_id)
        self.assertNotIn(settings.RAZORPAY_KEY_SECRET, response.content.decode())
        self.assertNotIn(settings.RAZORPAY_WEBHOOK_SECRET, response.content.decode())
        # Nothing is granted by starting a checkout.
        self.assertFalse(Subscription.objects.exists())

    def test_repeated_requests_reuse_the_unpaid_order(self):
        first, second = self.started(), self.started()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.razorpay.create_calls, 1)
        Purchase.objects.update(created_at=timezone.now() - timedelta(hours=1))
        self.assertNotEqual(self.started().pk, first.pk)

    def test_provider_error_records_no_successful_transaction(self):
        self.razorpay.fail_create = True
        response = self.start()
        self.assertEqual((response.status_code, response.json()["code"]), (503, "order_failed"))
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.status, PurchaseStatus.ORDER_FAILED)
        self.assertIsNone(purchase.razorpay_order_id)
        self.assertFalse(Subscription.objects.exists())

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_unavailable_without_keys(self):
        response = self.start()
        self.assertEqual((response.status_code, response.json()["code"]), (503, "payments_unavailable"))
        quote = self.client.get("/api/v1/payments/checkout/royal/").json()
        self.assertEqual((quote["available"], quote["blocked"]["code"]), (False, "payments_unavailable"))
        # No keys: the page must not claim Razorpay test keys are in use.
        self.assertFalse(quote["test_mode"])

    def test_needs_an_email_address(self):
        self.user.email = None
        self.user.save()
        response = self.start()
        self.assertEqual((response.status_code, response.json()["code"]), (409, "email_required"))
        self.assertEqual(self.razorpay.create_calls, 0)

    def test_an_active_membership_blocks_another_purchase(self):
        now = timezone.now()
        Subscription.objects.create(user=self.user, plan_code="gold", status=SubscriptionStatus.ACTIVE,
                                    starts_at=now, ends_at=now + timedelta(days=30))
        response = self.start()
        self.assertEqual((response.status_code, response.json()["code"]), (409, "membership_active"))

    def test_members_only(self):
        self.assertEqual(client_for().post(PURCHASES, {"package": "royal"}, format="json").status_code, 401)
        staff = make_user(role=Role.ADMIN)
        self.assertEqual(self.start(client=client_for(staff)).status_code, 403)


class ConfirmationTests(PaymentsTestCase):
    def test_valid_callback_with_captured_payment_activates_the_purchased_membership(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.callback(purchase, payment_id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "paid")

        purchase.refresh_from_db()
        self.assertEqual((purchase.status, purchase.razorpay_payment_id), (PurchaseStatus.PAID, payment_id))
        subscription = purchase.subscription
        self.assertEqual((subscription.user, subscription.plan_code, subscription.status), (self.user, "royal", "active"))
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, 12))
        self.assertEqual(subscription.package_fee, Decimal("100000.00"))
        self.assertTrue(subscription.is_current)
        # The member's existing membership API shows it.
        me = self.client.get("/api/v1/memberships/me/").json()
        self.assertEqual((me["current"]["plan_code"], me["entitlements"]["package_code"]), ("royal", "royal"))

    def test_invalid_signature_is_rejected(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id)
        for signature in ("0" * 64, sign(f"{purchase.razorpay_order_id}|{payment_id}", "wrong-secret"), "not-hex"):
            with self.subTest(signature=signature):
                response = self.callback(purchase, payment_id, signature=signature)
                self.assertEqual((response.status_code, response.json()["code"]), (400, "invalid_payment_signature"))
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, PurchaseStatus.AWAITING_PAYMENT)
        self.assertFalse(Subscription.objects.exists())

    def test_callback_for_another_order_or_member_is_rejected(self):
        mine = self.started()
        other_user = make_user(email="other@example.com")
        other_client = client_for(other_user)
        theirs = Purchase.objects.get(reference=self.start(client=other_client).json()["purchase"]["reference"])
        their_payment = self.razorpay.pay(theirs.razorpay_order_id)
        # Their (validly signed) payment can't be applied to my purchase...
        signature = sign(f"{theirs.razorpay_order_id}|{their_payment}", settings.RAZORPAY_KEY_SECRET)
        response = self.callback(mine, their_payment, signature=signature, order_id=theirs.razorpay_order_id)
        self.assertEqual(response.status_code, 400)
        # ...and I can't see or touch their purchase at all.
        self.assertEqual(self.callback(theirs, their_payment).status_code, 404)
        self.assertEqual(self.client.get(f"{PURCHASES}{theirs.reference}/").status_code, 404)
        self.assertFalse(Subscription.objects.exists())

    def test_captured_payment_with_the_wrong_amount_or_currency_grants_nothing(self):
        for amount, currency in ((100, "INR"), (ROYAL_TOTAL_PAISE, "USD")):
            with self.subTest(amount=amount, currency=currency):
                purchase = self.started()
                payment_id = self.razorpay.pay(purchase.razorpay_order_id, amount=amount, currency=currency)
                self.callback(purchase, payment_id)
                purchase.refresh_from_db()
                self.assertEqual(purchase.status, PurchaseStatus.NEEDS_REVIEW)
                self.assertFalse(Subscription.objects.exists())

    def test_authorized_but_not_captured_grants_nothing(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id, status="authorized")
        response = self.callback(purchase, payment_id)
        self.assertEqual(response.json()["status"], "authorized")
        self.assertFalse(Subscription.objects.exists())
        # Captured later (auto-capture): the status check activates it.
        self.razorpay.pay(purchase.razorpay_order_id, status="captured", payment_id=payment_id)
        self.assertEqual(self.client.post(f"{PURCHASES}{purchase.reference}/refresh/").json()["status"], "paid")
        self.assertEqual(Subscription.objects.count(), 1)

    def test_failed_and_pending_payments_grant_nothing_and_can_be_retried(self):
        purchase = self.started()
        self.assertEqual(self.client.post(f"{PURCHASES}{purchase.reference}/refresh/").json()["status"], "awaiting_payment")
        self.razorpay.pay(purchase.razorpay_order_id, status="failed", error_description="Payment declined by bank",
                          created_at=1)
        body = self.client.post(f"{PURCHASES}{purchase.reference}/refresh/").json()
        self.assertEqual((body["status"], body["failure_reason"], body["can_pay"]), ("failed", "Payment declined by bank", True))
        self.assertFalse(Subscription.objects.exists())
        # Retrying reopens the same order rather than creating another.
        self.assertEqual(self.started().pk, purchase.pk)
        self.assertEqual(self.razorpay.create_calls, 1)
        payment_id = self.razorpay.pay(purchase.razorpay_order_id, created_at=2)
        self.assertEqual(self.callback(purchase, payment_id).json()["status"], "paid")

    def test_provider_unreachable_after_a_valid_callback_is_not_a_failure(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id)
        self.razorpay.fail_fetch = True
        response = self.callback(purchase, payment_id)
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["confirmation_pending"])
        self.assertEqual(response.json()["status"], "awaiting_payment")
        self.assertFalse(Subscription.objects.exists())

    def test_repeated_callbacks_status_checks_and_webhooks_activate_once(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id)
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(3):
                self.callback(purchase, payment_id)
                self.client.post(f"{PURCHASES}{purchase.reference}/refresh/")
            self.assertEqual(self.webhook(self.event(purchase), event_id="evt_a").status_code, 200)
            self.assertEqual(self.webhook(self.event(purchase, "order.paid"), event_id="evt_b").status_code, 200)
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_payment_during_an_active_membership_starts_when_it_ends(self):
        purchase = self.started()
        now = timezone.now()
        current = Subscription.objects.create(user=self.user, plan_code="gold", status=SubscriptionStatus.ACTIVE,
                                              starts_at=now - timedelta(days=10), ends_at=now + timedelta(days=20))
        self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id))
        new = Purchase.objects.get().subscription
        self.assertEqual(new.starts_at, current.ends_at)
        self.assertEqual(new.ends_at, add_months(current.ends_at, 12))

    def test_list_and_detail_show_only_my_purchases(self):
        mine = self.started()
        other = make_user(email="x@example.com")
        self.start(client=client_for(other))
        body = self.client.get(PURCHASES).json()
        self.assertEqual([item["reference"] for item in body["results"]], [mine.reference])
        detail = self.client.get(f"{PURCHASES}{mine.reference}/").json()
        self.assertEqual(detail["checkout"]["order_id"], mine.razorpay_order_id)


class WebhookTests(PaymentsTestCase):
    def test_signature_is_checked_on_the_raw_body(self):
        purchase = self.started()
        self.razorpay.pay(purchase.razorpay_order_id)
        bad = self.webhook(self.event(purchase), secret="wrong")
        self.assertEqual(bad.status_code, 400)
        # The API key secret is not the webhook secret.
        self.assertEqual(self.webhook(self.event(purchase), secret=settings.RAZORPAY_KEY_SECRET).status_code, 400)
        raw = json.dumps(self.event(purchase)).encode()
        tampered = self.client.generic(
            "POST", WEBHOOK, raw.replace(b"captured", b"failed"), content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=sign(raw.decode(), settings.RAZORPAY_WEBHOOK_SECRET),
        )
        self.assertEqual(tampered.status_code, 400)
        self.assertFalse(Subscription.objects.exists())

    def test_captured_event_activates_after_checking_razorpay(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.webhook(self.event(purchase, payment_id=payment_id))
        self.assertEqual(response.status_code, 200)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, PurchaseStatus.PAID)
        event = WebhookEvent.objects.get()
        self.assertEqual((event.status, event.purchase), ("processed", purchase))

    def test_payload_alone_proves_nothing(self):
        purchase = self.started()
        # A correctly signed "captured" event, but Razorpay's API has no captured payment.
        self.assertEqual(self.webhook(self.event(purchase)).status_code, 200)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, PurchaseStatus.AWAITING_PAYMENT)
        self.assertFalse(Subscription.objects.exists())

    def test_duplicate_and_late_events(self):
        purchase = self.started()
        self.razorpay.pay(purchase.razorpay_order_id)
        self.webhook(self.event(purchase), event_id="evt_1")
        again = self.webhook(self.event(purchase), event_id="evt_1")
        self.assertEqual((again.status_code, again.json()["detail"]), (200, "Already processed."))
        self.assertEqual(WebhookEvent.objects.get().deliveries, 2)
        # A late "authorized" or "failed" can't take a paid purchase backwards.
        self.webhook(self.event(purchase, "payment.authorized"), event_id="evt_2")
        self.webhook(self.event(purchase, "payment.failed"), event_id="evt_3")
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, PurchaseStatus.PAID)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_failed_event_records_failure_without_membership(self):
        purchase = self.started()
        self.razorpay.pay(purchase.razorpay_order_id, status="failed", error_description="Card declined")
        self.webhook(self.event(purchase, "payment.failed"))
        purchase.refresh_from_db()
        self.assertEqual((purchase.status, purchase.failure_reason), (PurchaseStatus.FAILED, "Card declined"))
        self.assertFalse(Subscription.objects.exists())

    def test_unknown_orders_and_events_are_acknowledged_and_ignored(self):
        purchase = self.started()
        self.assertEqual(self.webhook({"event": "refund.created", "payload": {}}, event_id="e1").status_code, 200)
        purchase.razorpay_order_id = "order_UNKNOWN0000"
        self.assertEqual(self.webhook(self.event(purchase), event_id="e2").status_code, 200)
        self.assertEqual(set(WebhookEvent.objects.values_list("status", flat=True)), {"ignored"})

    def test_razorpay_unreachable_asks_for_a_retry(self):
        purchase = self.started()
        self.razorpay.fail_fetch = True
        self.assertEqual(self.webhook(self.event(purchase)).status_code, 503)
        self.assertEqual(WebhookEvent.objects.get().status, "failed")
        # The retry is processed once Razorpay is reachable.
        self.razorpay.fail_fetch = False
        self.razorpay.pay(purchase.razorpay_order_id)
        self.assertEqual(self.webhook(self.event(purchase)).status_code, 200)
        self.assertEqual(Purchase.objects.get().status, PurchaseStatus.PAID)

    @override_settings(RAZORPAY_WEBHOOK_SECRET="")
    def test_unconfigured_webhook_secret(self):
        response = self.client.generic("POST", WEBHOOK, b"{}", content_type="application/json")
        self.assertEqual(response.status_code, 503)

    def test_only_post(self):
        self.assertEqual(self.client.get(WEBHOOK).status_code, 405)


class ReceiptTests(PaymentsTestCase):
    def pay(self):
        purchase = self.started()
        payment_id = self.razorpay.pay(purchase.razorpay_order_id)
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, payment_id)
        purchase.refresh_from_db()
        return purchase

    def test_receipt_is_issued_numbered_and_emailed_to_the_registered_address(self):
        purchase = self.pay()
        receipt = purchase.receipt
        year = financial_year(receipt.issued_at)
        self.assertEqual(receipt.number, f"MM/{year}/000001")
        self.assertEqual(receipt.email_status, EmailStatus.SENT)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["anu@example.com"])
        self.assertIn(receipt.number, message.subject)
        self.assertTrue(message.subject.startswith("[TEST]"))
        self.assertIn("118,000.00", message.body)
        self.assertIn(purchase.razorpay_payment_id, message.body)
        self.assertIn(f"/dashboard/membership/receipts/{receipt.public_id}", message.body)
        html = message.alternatives[0][0]
        self.assertIn("Payment Receipt", html)
        self.assertNotIn(self.user.phone_number, message.subject)

    def test_receipt_goes_to_the_email_at_purchase_time_not_a_changed_one(self):
        purchase = self.started()
        self.client.patch("/api/v1/auth/me/email/", {"email": "new@example.com"}, format="json")
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id))
        self.assertEqual(mail.outbox[0].to, ["anu@example.com"])

    def test_numbers_are_sequential_per_financial_year(self):
        self.assertEqual(financial_year(datetime(2027, 3, 31, 12, tzinfo=dt_timezone.utc)), "2026-27")
        self.assertEqual(financial_year(datetime(2027, 4, 1, 12, tzinfo=dt_timezone.utc)), "2027-28")
        first = self.pay().receipt.number
        other = make_user(email="b@example.com")
        purchase = Purchase.objects.get(reference=self.start(client=client_for(other)).json()["purchase"]["reference"])
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id), client=client_for(other))
        second = Purchase.objects.get(pk=purchase.pk).receipt.number
        self.assertEqual(int(second.rsplit("/", 1)[1]), int(first.rsplit("/", 1)[1]) + 1)

    def test_email_failure_keeps_the_payment_and_is_retried(self):
        with mock.patch("apps.payments.receipts.send_email", side_effect=EmailError("Email not sent (SMTPConnectError)")):
            purchase = self.pay()
        receipt = purchase.receipt
        self.assertEqual((receipt.email_status, receipt.email_attempts), (EmailStatus.FAILED, 1))
        self.assertEqual(purchase.status, PurchaseStatus.PAID)
        self.assertTrue(purchase.subscription.is_current)

        out = StringIO()
        call_command("retry_receipt_emails", stdout=out)
        receipt.refresh_from_db()
        self.assertEqual((receipt.email_status, receipt.email_attempts), (EmailStatus.SENT, 2))
        self.assertIn("accepted: 1", out.getvalue())
        call_command("retry_receipt_emails", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)  # never sent twice

    @override_settings(RECEIPT_EMAIL_MAX_ATTEMPTS=2)
    def test_retries_stop_after_the_limit(self):
        with mock.patch("apps.payments.receipts.send_email", side_effect=EmailError("down")):
            purchase = self.pay()
            call_command("retry_receipt_emails", stdout=StringIO())
            call_command("retry_receipt_emails", stdout=StringIO())
        receipt = Receipt.objects.get(purchase=purchase)
        self.assertEqual((receipt.email_status, receipt.email_attempts), (EmailStatus.GAVE_UP, 2))

    def test_no_receipt_for_unpaid_purchases(self):
        purchase = self.started()
        self.razorpay.pay(purchase.razorpay_order_id, status="failed")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"{PURCHASES}{purchase.reference}/refresh/")
        self.assertFalse(Receipt.objects.exists())
        self.assertEqual(mail.outbox, [])
        call_command("retry_receipt_emails", stdout=StringIO())
        self.assertFalse(Receipt.objects.exists())

    def test_receipt_api_is_for_its_owner_only(self):
        receipt = self.pay().receipt
        url = f"/api/v1/payments/receipts/{receipt.public_id}/"
        body = self.client.get(url).json()
        self.assertEqual((body["number"], body["amounts"]["total"], body["title"]), (receipt.number, "118000.00", "Payment Receipt"))
        self.assertEqual(client_for(make_user(email="z@example.com")).get(url).status_code, 404)
        self.assertEqual(client_for().get(url).status_code, 401)

    @override_settings(BILLING_SELLER_NAME="Example Matrimony Pvt Ltd", BILLING_SELLER_GSTIN="32ABCDE1234F1Z5")
    def test_seller_details_come_only_from_settings(self):
        receipt = self.pay().receipt
        self.assertEqual(receipt.seller["legal_name"], "Example Matrimony Pvt Ltd")
        self.assertIn("GSTIN: 32ABCDE1234F1Z5", mail.outbox[0].body)

    def test_without_configured_seller_details_nothing_is_invented(self):
        receipt = self.pay().receipt
        self.assertEqual((receipt.seller["legal_name"], receipt.seller["gstin"], receipt.seller["address"]), ("", "", ""))
        self.assertNotIn("GSTIN", mail.outbox[0].body)


class AdminTests(PaymentsTestCase):
    def setUp(self):
        super().setUp()
        self.purchase = self.started()
        self.razorpay.pay(self.purchase.razorpay_order_id)

    def test_superuser_sees_purchases_and_cannot_edit_or_mark_paid(self):
        root = make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.client.force_login(root)
        changelist = reverse("admin:payments_purchase_changelist")
        self.assertContains(self.client.get(changelist), self.purchase.reference)
        page = self.client.get(reverse("admin:payments_purchase_change", args=[self.purchase.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'name="status"')
        self.client.post(reverse("admin:payments_purchase_change", args=[self.purchase.pk]), {"status": "paid"})
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PurchaseStatus.AWAITING_PAYMENT)
        self.assertEqual(self.client.get(reverse("admin:payments_purchase_add")).status_code, 403)

        # The only way to "paid" is asking Razorpay.
        self.client.post(changelist, {"action": "check_with_razorpay", "_selected_action": [self.purchase.pk]})
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PurchaseStatus.PAID)

    def test_staff_need_the_view_permission(self):
        staff = make_user(role=Role.ADMIN, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("admin:payments_purchase_changelist")).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_purchase"))
        self.assertEqual(self.client.get(reverse("admin:payments_purchase_changelist")).status_code, 200)
        # Viewing doesn't allow the status-check action.
        self.client.post(reverse("admin:payments_purchase_changelist"),
                         {"action": "check_with_razorpay", "_selected_action": [self.purchase.pk]})
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PurchaseStatus.AWAITING_PAYMENT)


class EmailUpdateTests(PaymentsTestCase):
    URL = "/api/v1/auth/me/email/"

    def test_member_corrects_their_own_email(self):
        response = self.client.patch(self.URL, {"email": " New.Address@Example.COM "}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new.address@example.com")

    def test_invalid_or_taken_addresses_are_refused(self):
        make_user(email="taken@example.com")
        for value in ("", "nope", "TAKEN@example.com"):
            with self.subTest(email=value):
                self.assertEqual(self.client.patch(self.URL, {"email": value}, format="json").status_code, 400)
        # Nothing in the request can select another account.
        other = make_user(email="other@example.com")
        self.client.patch(self.URL, {"email": "mine@example.com", "user": str(other.public_id)}, format="json")
        other.refresh_from_db()
        self.assertEqual(other.email, "other@example.com")
        self.assertEqual(client_for().patch(self.URL, {"email": "a@example.com"}, format="json").status_code, 401)


class LiveModeSafetyTests(TestCase):
    def load(self, settings_module, **overrides):
        mine = ("EMAIL_", "DEFAULT_FROM_EMAIL", "FRONTEND_URL", "SMS_", "MSG91_", "RAZORPAY_", "BILLING_", "MEMBERSHIP_")
        env = {
            **{key: value for key, value in os.environ.items() if not key.startswith(mine)},
            "DJANGO_READ_ENV_FILE": "False", "DJANGO_SECRET_KEY": "x" * 60, "DJANGO_ALLOWED_HOSTS": "api.example.com",
            "CORS_ALLOWED_ORIGINS": "https://example.com", "CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DB_NAME": "db", "DB_USER": "user", "DB_PASSWORD": "pass", **overrides,
        }
        result = subprocess.run([sys.executable, "-c", f"import {settings_module}"], cwd=settings.BASE_DIR, env=env,
                                capture_output=True, text=True, timeout=60)
        return result.returncode, result.stderr

    def test_key_must_match_the_mode(self):
        code, stderr = self.load("config.settings.production", RAZORPAY_MODE="test", RAZORPAY_KEY_ID="rzp_live_abc")
        self.assertNotEqual(code, 0)
        self.assertIn("rzp_test_", stderr)

    def test_live_mode_needs_everything_a_paying_customer_is_owed(self):
        code, stderr = self.load("config.settings.production", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_abc",
                                 RAZORPAY_KEY_SECRET="s")
        self.assertNotEqual(code, 0)
        for name in ("RAZORPAY_WEBHOOK_SECRET", "BILLING_SELLER_NAME", "BILLING_SELLER_ADDRESS", "EMAIL_PROVIDER=smtp"):
            self.assertIn(name, stderr)

    def test_live_mode_is_refused_in_development(self):
        code, stderr = self.load("config.settings.development", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_abc")
        self.assertNotEqual(code, 0)
        self.assertIn("refused in development", stderr)


class ExistingFeaturesTests(PaymentsTestCase):
    def test_package_list_still_shows_prices_without_inventing_gst(self):
        packages = {item["code"]: item for item in client_for().get("/api/v1/memberships/packages/").json()}
        self.assertEqual(packages["royal"]["total_payable"], "118000.00")
        self.assertIsNone(packages["silver"]["total_payable"])
        self.assertIsNone(packages["silver"]["gst_rate"])
        self.assertEqual(packages[PackageCode.FREE]["total_payable"], "0.00")

    def test_paid_membership_grants_its_contact_limit(self):
        purchase = self.started()
        self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id))
        me = self.client.get("/api/v1/memberships/me/").json()
        self.assertEqual(me["entitlements"]["package_code"], "royal")
        self.assertIsNone(me["entitlements"]["outgoing_interest_limit"])
