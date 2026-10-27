"""
Membership purchase figures for the admin (Membership Purchases > Summary and
the admin dashboard). Every figure is one database aggregate over Purchase,
with these rules:

- One purchase = one Razorpay order for one package. Retries inside an order
  are RazorpayPayment rows, and repeated webhooks are WebhookEvent rows, so
  neither is ever counted as another purchase or another payment.
- "Paid" means verified with Razorpay's API and captured for the exact amount
  (PurchaseStatus.PAID); only those count as revenue.
- Revenue counts live-mode purchases only. Test-mode payments (rzp_test_ keys)
  move no real money and are shown separately.
- Gross collected = the totals (fee + GST) of paid purchases. Refunded = what
  Razorpay reports refunded on those payments. Net = gross - refunded.
- "This month" is the calendar month in India time (TIME_ZONE), by paid date.
- Membership states come from the membership each paid purchase created
  (Subscription), using the same rule as entitlements: active = active status
  and inside its period. Payment status and membership status are separate:
  a paid purchase can have an expired membership.

Staff-recorded offline memberships have no Purchase and aren't counted here;
the dashboard's "Active memberships" counts every membership.
"""
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.memberships.models import SubscriptionStatus

from .models import Purchase, PurchaseStatus, RefundStatus

PENDING = (PurchaseStatus.AWAITING_PAYMENT, PurchaseStatus.AUTHORIZED)
FAILED = (PurchaseStatus.FAILED, PurchaseStatus.ORDER_FAILED)
LIVE = "live"


def month_start(now=None):
    local = timezone.localtime(now or timezone.now())
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def membership_state(purchase, now=None) -> tuple[str, str]:
    """(code, label) of what the purchase's membership is now, kept apart from its payment status."""
    if purchase.status != PurchaseStatus.PAID:
        if purchase.status in PENDING:
            return "pending_payment", "Pending payment"
        if purchase.status in FAILED:
            return "payment_failed", "Payment failed"
        return "under_review", "Payment under review"
    subscription = purchase.subscription
    if subscription is None:
        return "none", "No membership"
    if subscription.status == SubscriptionStatus.CANCELLED:
        return "cancelled", "Cancelled"
    now = now or timezone.now()
    if subscription.ends_at and subscription.ends_at <= now:
        return "expired", "Expired"
    if subscription.starts_at and subscription.starts_at > now:
        return "upcoming", "Starts later"
    return "active", "Active"


def membership_q(state: str, now=None) -> Q:
    """Purchases whose membership is in `state` (membership_state's codes for paid purchases)."""
    now = now or timezone.now()
    paid = Q(status=PurchaseStatus.PAID)
    active_status = Q(subscription__status=SubscriptionStatus.ACTIVE)
    return {
        "active": paid & active_status & Q(subscription__starts_at__lte=now, subscription__ends_at__gt=now),
        "upcoming": paid & active_status & Q(subscription__starts_at__gt=now),
        "expired": paid & active_status & Q(subscription__ends_at__lte=now),
        "cancelled": paid & Q(subscription__status=SubscriptionStatus.CANCELLED),
        "pending_payment": Q(status__in=PENDING),
        "payment_failed": Q(status__in=FAILED),
        "under_review": Q(status=PurchaseStatus.NEEDS_REVIEW),
    }[state]


def _money(field, condition):
    return Coalesce(Sum(field, filter=condition), Value(Decimal("0")), output_field=DecimalField(max_digits=14, decimal_places=2))


def summary(queryset=None, now=None) -> dict:
    """All the counts and amounts, in one query."""
    now = now or timezone.now()
    queryset = Purchase.objects.all() if queryset is None else queryset
    paid, live = Q(status=PurchaseStatus.PAID), Q(mode=LIVE)
    refunded = ~Q(refund_status=RefundStatus.NONE)
    figures = queryset.aggregate(
        total=Count("pk"),
        paid=Count("pk", filter=paid),
        active=Count("pk", filter=membership_q("active", now)),
        upcoming=Count("pk", filter=membership_q("upcoming", now)),
        expired=Count("pk", filter=membership_q("expired", now)),
        cancelled=Count("pk", filter=membership_q("cancelled", now)),
        pending=Count("pk", filter=Q(status__in=PENDING)),
        failed=Count("pk", filter=Q(status__in=FAILED)),
        needs_review=Count("pk", filter=Q(status=PurchaseStatus.NEEDS_REVIEW)),
        refunded=Count("pk", filter=paid & refunded),
        gross=_money("total_amount", paid & live),
        gross_month=_money("total_amount", paid & live & Q(paid_at__gte=month_start(now))),
        gst=_money("gst_amount", paid & live),
        refunded_paise=Coalesce(Sum("refunded_amount_subunits", filter=paid & live), Value(0)),
        test_paid=Count("pk", filter=paid & ~live),
        test_gross=_money("total_amount", paid & ~live),
    )
    figures["refunded_amount"] = Decimal(figures.pop("refunded_paise")) / 100
    figures["net"] = figures["gross"] - figures["refunded_amount"]
    return figures


def by_package(queryset=None, now=None) -> list[dict]:
    """Paid purchases, active memberships and live gross per package, one query."""
    now = now or timezone.now()
    queryset = Purchase.objects.all() if queryset is None else queryset
    paid = Q(status=PurchaseStatus.PAID)
    rows = (
        queryset.order_by().values("package_code", "package_name")
        .annotate(
            purchases=Count("pk"),
            paid=Count("pk", filter=paid),
            active=Count("pk", filter=membership_q("active", now)),
            gross=_money("total_amount", paid & Q(mode=LIVE)),
        )
        .order_by("package_code")
    )
    merged = {}
    for row in rows:  # one row per package, under its latest name
        item = merged.setdefault(row["package_code"], {**row, "purchases": 0, "paid": 0, "active": 0, "gross": Decimal("0")})
        for key in ("purchases", "paid", "active", "gross"):
            item[key] += row[key]
    return list(merged.values())
