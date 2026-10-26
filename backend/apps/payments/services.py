"""
Buying a membership package online with Razorpay.

1. start_checkout: the member picks a package by code. The price, GST,
   currency and validity come from MembershipPackage (never the browser). A
   Purchase is recorded with a snapshot of those terms, and a Razorpay order is
   created for exactly that amount in paise. A repeated request reuses the
   member's recent unpaid order for the same package instead of creating another.
2. The browser opens Razorpay Checkout for that order. Its success callback
   is only a hint: verify_checkout checks the signature against the order id
   stored here, then calls reconcile.
3. reconcile asks Razorpay's API for the order's payments and decides. A
   payment counts only when Razorpay reports it "captured" for this order with
   exactly the purchase's amount and currency. "authorized" is not paid. The
   checkout callback, the status-check button and webhooks all end here, so
   whichever arrives first activates the membership and the rest change nothing.
4. Paying creates one active Subscription with the purchased terms, under a
   row lock, exactly once; then the receipt is issued and emailed
   (apps.payments.receipts).

Purchase rules (an explicit policy, until the business decides otherwise):
- A member with a current paid membership can't buy another online; they
  contact the team to renew or upgrade. Nothing is stacked, reset or shortened.
- If a payment is confirmed while another membership is active anyway (e.g.
  staff activated one meanwhile), the new one starts when the current one ends.
- Free membership needs no purchase. A package priced "plus applicable GST" can't
  be bought until MEMBERSHIP_GST_RATE_PERCENT is configured.
"""
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.memberships.models import MembershipPackage, Subscription, SubscriptionStatus, add_months

from . import razorpay_api
from .models import Purchase, PurchaseStatus, RazorpayPayment
from .razorpay_api import RazorpayError

logger = logging.getLogger(__name__)

CURRENCY = "INR"
# An unpaid order is reused for repeat checkout requests within this time.
ORDER_REUSE_WINDOW = timedelta(minutes=30)
SITE_NAME = "Massil Matrimony"


class CheckoutError(Exception):
    code = "checkout_error"
    status = 400
    message = "This purchase can't be started."

    def __init__(self, message=None):
        self.message = message or self.message
        super().__init__(self.message)


class PaymentsUnavailable(CheckoutError):
    code, status = "payments_unavailable", 503
    message = "Online payment isn't available right now. Please contact us to buy a package."


class PackageNotFound(CheckoutError):
    code, status = "package_not_found", 404
    message = "This package isn't available."


class NotPurchasable(CheckoutError):
    code, status = "not_purchasable", 409
    message = "This package can't be bought online."


class PriceNotConfirmed(CheckoutError):
    code, status = "price_not_confirmed", 409
    message = "The price including GST for this package isn't confirmed yet, so it can't be bought online. Please contact us."


class EmailRequired(CheckoutError):
    code, status = "email_required", 409
    message = "Add your email address in Account Settings first: we send your payment receipt there."


class MembershipActive(CheckoutError):
    code, status = "membership_active", 409
    message = "You already have an active membership. Please contact us to renew or upgrade it."


class OrderFailed(CheckoutError):
    code, status = "order_failed", 503
    message = "We couldn't start the payment just now. Nothing was charged. Please try again in a few minutes."


# --- Price -------------------------------------------------------------------------


@dataclass(frozen=True)
class Quote:
    package: MembershipPackage
    base: Decimal
    gst_rate: Decimal
    gst: Decimal
    total: Decimal
    amount_subunits: int
    currency: str = CURRENCY


def to_subunits(amount: Decimal) -> int:
    """Rupees (2 decimal places) to paise, exactly."""
    subunits = amount * 100
    if subunits != subunits.to_integral_value():
        raise ValueError("Amounts must be whole paise.")
    return int(subunits)


def quote(package: MembershipPackage) -> Quote:
    """The price of `package`, from the package itself. Raises NotPurchasable or PriceNotConfirmed."""
    if package.is_free:
        raise NotPurchasable("Free membership needs no payment.")
    total, gst, rate = package.total_payable, package.gst_amount, package.gst_rate
    if total is None or gst is None or rate is None:
        raise PriceNotConfirmed()
    if total <= 0 or not package.validity_months:
        raise NotPurchasable()
    return Quote(package, package.fee, rate, gst, total, to_subunits(total))


# --- Starting a purchase ---------------------------------------------------------------


def purchasable_package(code: str) -> MembershipPackage:
    package = MembershipPackage.objects.available().filter(code=code).first()
    if package is None:
        raise PackageNotFound()
    return package


def has_current_membership(user) -> bool:
    return Subscription.objects.current().filter(user=user).exists()


def check_checkout(user, package: MembershipPackage) -> Quote:
    """The quote if `user` may buy `package` online now; otherwise the CheckoutError saying why not."""
    if not razorpay_api.configured():
        raise PaymentsUnavailable()
    price = quote(package)
    if not user.email:
        raise EmailRequired()
    if has_current_membership(user):
        raise MembershipActive()
    return price


def _new_reference() -> str:
    # e.g. MMP-20261026-7KQ2M9XA: unguessable enough not to be a lookup key on its own,
    # and every lookup is also filtered by the signed-in member.
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return f"MMP-{timezone.localdate():%Y%m%d}-{''.join(secrets.choice(alphabet) for _ in range(8))}"


def start_checkout(user, package_code: str) -> Purchase:
    """A Purchase with a Razorpay order the member can pay (new, or their recent unpaid one)."""
    package = purchasable_package(package_code)
    error = None
    with transaction.atomic():
        # One checkout at a time per member, so repeated clicks can't create parallel orders.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        user.refresh_from_db(fields=["email", "phone_number", "first_name", "last_name"])
        price = check_checkout(user, package)

        reusable = (
            Purchase.objects.filter(
                user=user,
                package=package,
                # A failed attempt can be retried on the same Razorpay order.
                status__in=[PurchaseStatus.AWAITING_PAYMENT, PurchaseStatus.FAILED],
                amount_subunits=price.amount_subunits,
                currency=price.currency,
                billing_email=user.email,
                mode=settings.RAZORPAY_MODE,
                razorpay_order_id__isnull=False,
                created_at__gte=timezone.now() - ORDER_REUSE_WINDOW,
            )
            .order_by("-created_at")
            .first()
        )
        if reusable:
            return reusable

        purchase = Purchase.objects.create(
            reference=_new_reference(),
            user=user,
            package=package,
            mode=settings.RAZORPAY_MODE,
            package_code=package.code,
            package_name=package.name,
            validity_months=package.validity_months,
            contact_view_limit=package.contact_view_limit,
            tax_treatment=package.tax_treatment,
            base_amount=price.base,
            gst_rate=price.gst_rate,
            gst_amount=price.gst,
            total_amount=price.total,
            amount_subunits=price.amount_subunits,
            currency=price.currency,
            billing_name=user.full_name,
            billing_email=user.email,
            billing_phone=user.phone_number or "",
        )
        try:
            # Notes hold no personal data: they appear in Razorpay's dashboard and reports.
            order = razorpay_api.create_order(
                price.amount_subunits, price.currency, purchase.reference,
                {"purchase": purchase.reference, "package": package.code},
            )
        except RazorpayError as exc:
            logger.error("Razorpay order not created for purchase %s: %s", purchase.reference, exc)
            purchase.status = PurchaseStatus.ORDER_FAILED
            purchase.failure_reason = "The payment couldn't be started."
            purchase.save(update_fields=["status", "failure_reason", "updated_at"])
            error = OrderFailed()
        else:
            purchase.razorpay_order_id = order["id"]
            purchase.save(update_fields=["razorpay_order_id", "updated_at"])
            logger.info("Purchase %s: Razorpay order %s created", purchase.reference, order["id"])
    if error:
        raise error
    return purchase


def checkout_options(purchase: Purchase) -> dict:
    """What the browser needs to open Razorpay Checkout. The key id is public; no secret is included."""
    return {
        "key": settings.RAZORPAY_KEY_ID,
        "order_id": purchase.razorpay_order_id,
        "amount": purchase.amount_subunits,
        "currency": purchase.currency,
        "name": SITE_NAME,
        "description": f"{purchase.package_name} ({purchase.validity_months} months)",
        "prefill": {"name": purchase.billing_name, "email": purchase.billing_email, "contact": purchase.billing_phone},
        "test_mode": purchase.mode == "test",
    }


# --- Confirming payment --------------------------------------------------------------


def _timestamp(value):
    try:
        return datetime.fromtimestamp(int(value), tz=dt_timezone.utc) if value else None
    except (TypeError, ValueError, OverflowError):
        return None


def _record_payment(purchase: Purchase, item: dict) -> None:
    RazorpayPayment.objects.update_or_create(
        payment_id=str(item.get("id", ""))[:40],
        defaults={
            "purchase": purchase,
            "status": str(item.get("status", ""))[:12],
            "amount_subunits": int(item.get("amount") or 0),
            "currency": str(item.get("currency", ""))[:3],
            "method": str(item.get("method") or "")[:20],
            "error_code": str(item.get("error_code") or "")[:60],
            "error_description": str(item.get("error_description") or "")[:255],
            "razorpay_created_at": _timestamp(item.get("created_at")),
        },
    )


def _activate(purchase: Purchase, now) -> Subscription:
    """Grant the purchased membership. Starts now, or when the member's latest active membership ends."""
    later = (
        Subscription.objects.select_for_update()
        .filter(user=purchase.user, status=SubscriptionStatus.ACTIVE, ends_at__gt=now)
        .order_by("-ends_at")
        .first()
    )
    starts_at = later.ends_at if later else now
    subscription = Subscription(
        user=purchase.user,
        plan_code=purchase.package_code,
        status=SubscriptionStatus.ACTIVE,
        starts_at=starts_at,
        ends_at=add_months(starts_at, purchase.validity_months),
        package_fee=purchase.base_amount,
        validity_months=purchase.validity_months,
        contact_view_limit=purchase.contact_view_limit,
        staff_note=f"Paid online, purchase {purchase.reference}.",
    )
    subscription.save()
    return subscription


def reconcile(purchase: Purchase) -> Purchase:
    """
    Bring the purchase up to date with Razorpay's own record of the order's
    payments. Raises RazorpayError if Razorpay can't be asked (nothing changes).
    Safe to call any number of times, from any path.
    """
    if not purchase.razorpay_order_id:
        return purchase
    items = [item for item in razorpay_api.order_payments(purchase.razorpay_order_id) if item.get("id")]
    paid_now = False
    with transaction.atomic():
        locked = Purchase.objects.select_for_update().get(pk=purchase.pk)
        order_id = locked.razorpay_order_id
        ours = [item for item in items if item.get("order_id") == order_id]
        for item in ours:
            _record_payment(locked, item)
        locked.last_checked_at = timezone.now()
        fields = ["last_checked_at", "updated_at"]

        if locked.status != PurchaseStatus.PAID:
            captured = [item for item in ours if item.get("status") == "captured"]
            exact = [
                item for item in captured
                if item.get("amount") == locked.amount_subunits and item.get("currency") == locked.currency
            ]
            newest = max(ours, key=lambda item: item.get("created_at") or 0, default=None)
            if exact:
                payment = exact[0]
                now = timezone.now()
                locked.subscription = _activate(locked, now)
                locked.status = PurchaseStatus.PAID
                locked.razorpay_payment_id = payment["id"]
                locked.paid_at = _timestamp(payment.get("created_at")) or now
                locked.failure_reason = ""
                fields += ["subscription", "status", "razorpay_payment_id", "paid_at", "failure_reason"]
                paid_now = True
                logger.info("Purchase %s paid by %s; membership activated", locked.reference, payment["id"])
            elif captured or any(item.get("status") == "refunded" for item in ours):
                locked.status = PurchaseStatus.NEEDS_REVIEW
                fields.append("status")
                logger.warning("Purchase %s: captured/refunded payment doesn't match; needs review", locked.reference)
            elif any(item.get("status") == "authorized" for item in ours):
                locked.status = PurchaseStatus.AUTHORIZED
                fields.append("status")
            elif newest is not None and newest.get("status") == "failed":
                locked.status = PurchaseStatus.FAILED
                locked.failure_reason = str(newest.get("error_description") or "The payment didn't go through.")[:255]
                fields += ["status", "failure_reason"]
        locked.save(update_fields=fields)

    if paid_now:
        from .receipts import fulfil

        # After the commit, so the payment and membership stand even if the receipt step fails.
        transaction.on_commit(lambda: fulfil(locked.pk))
    return locked


def verify_checkout(purchase: Purchase, order_id: str, payment_id: str, signature: str) -> Purchase:
    """
    Handle Razorpay Checkout's success callback. The signature must match the
    order id stored on the purchase; then Razorpay's API decides (reconcile).
    Raises InvalidCallback for a bad or mismatched callback, RazorpayError if Razorpay can't be asked.
    """
    if order_id != purchase.razorpay_order_id or not razorpay_api.checkout_signature_valid(
        purchase.razorpay_order_id, payment_id, signature
    ):
        logger.warning("Purchase %s: checkout callback with an invalid signature or order", purchase.reference)
        raise InvalidCallback()
    return reconcile(purchase)


class InvalidCallback(CheckoutError):
    code, status = "invalid_payment_signature", 400
    message = "We couldn't verify this payment. If money was taken, it will be confirmed shortly or refunded by Razorpay."
