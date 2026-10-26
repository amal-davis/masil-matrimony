"""
Online membership purchases through Razorpay (see apps.payments.services).

- Purchase: one attempt to buy one package, with an immutable snapshot of what
  was sold (package, fee, GST, total, validity, contact limit, billing contact)
  taken from MembershipPackage when the order was created. Later package
  edits never change it.
- RazorpayPayment: each payment Razorpay reports against the purchase's order
  (a member can fail and retry within one order).
- Receipt: the payment receipt issued once a purchase is paid, with its own
  numbering and email delivery record.
- WebhookEvent: Razorpay webhook deliveries, by event id, for idempotency and
  troubleshooting.

Gateway secrets come from environment variables only and are never stored here.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class PurchaseStatus(models.TextChoices):
    # Razorpay order created; the member hasn't paid yet (or closed the checkout).
    AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
    # The bank approved a payment but it isn't captured: not paid, grants nothing.
    AUTHORIZED = "authorized", "Authorised, not captured"
    # Captured, verified with Razorpay's API, membership granted.
    PAID = "paid", "Paid"
    # The latest payment attempt failed. The member may retry the same order.
    FAILED = "failed", "Payment failed"
    # Razorpay reported a captured payment that doesn't match this purchase (amount, currency
    # or order). Nothing is granted; staff must investigate.
    NEEDS_REVIEW = "needs_review", "Needs review"
    # The Razorpay order couldn't be created. Nothing was charged.
    ORDER_FAILED = "order_failed", "Couldn't start payment"


class Purchase(TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # Shown to the member and sent to Razorpay as the order receipt (max 40 characters).
    reference = models.CharField(max_length=40, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases")
    package = models.ForeignKey("memberships.MembershipPackage", on_delete=models.PROTECT, related_name="purchases")
    status = models.CharField(
        max_length=20, choices=PurchaseStatus.choices, default=PurchaseStatus.AWAITING_PAYMENT, db_index=True
    )
    # "test" or "live": the Razorpay mode the order was created in.
    mode = models.CharField(max_length=4)

    # What was sold, copied from the package when the order was created.
    package_code = models.CharField(max_length=16)
    package_name = models.CharField(max_length=80)
    validity_months = models.PositiveSmallIntegerField()
    contact_view_limit = models.PositiveIntegerField(null=True, blank=True)
    tax_treatment = models.CharField(max_length=12)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Rupees, excluding GST.")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percent.")
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    # The total in paise, exactly as sent to Razorpay.
    amount_subunits = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="INR")

    # Who receipts go to: the member's registered details when the order was created.
    billing_name = models.CharField(max_length=150, blank=True)
    billing_email = models.EmailField(max_length=254)
    billing_phone = models.CharField(max_length=16, blank=True)

    razorpay_order_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    # The captured payment that paid for this purchase.
    razorpay_payment_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Short, member-safe explanation of the latest failure (from Razorpay's error description).
    failure_reason = models.CharField(max_length=255, blank=True)
    # The membership this purchase granted. Set exactly once, when it is paid.
    subscription = models.OneToOneField(
        "memberships.Subscription", null=True, blank=True, on_delete=models.PROTECT, related_name="purchase"
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="paid") | (Q(razorpay_payment_id__isnull=False) & Q(paid_at__isnull=False)),
                name="payments_paid_purchase_has_payment",
            ),
        ]

    def __str__(self):
        return f"{self.reference} ({self.package_name})"


class RazorpayPayment(TimeStampedModel):
    """A payment Razorpay reported for a purchase's order, as last fetched from Razorpay's API."""

    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="payments")
    payment_id = models.CharField(max_length=40, unique=True)
    # created, authorized, captured, refunded or failed (Razorpay's payment states).
    status = models.CharField(max_length=12)
    amount_subunits = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=20, blank=True)
    error_code = models.CharField(max_length=60, blank=True)
    error_description = models.CharField(max_length=255, blank=True)
    razorpay_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Razorpay payment"

    def __str__(self):
        return f"{self.payment_id} ({self.status})"


class EmailStatus(models.TextChoices):
    PENDING = "pending", "Not sent yet"
    # Handed to the mail server; not proof that it reached the inbox.
    SENT = "sent", "Accepted by mail server"
    FAILED = "failed", "Failed (will retry)"
    GAVE_UP = "gave_up", "Failed (no more retries)"


class Receipt(models.Model):
    """
    The payment receipt for a paid purchase. Not a GST tax invoice: see
    apps.payments.receipts. Seller and buyer details are copied when issued.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    number = models.CharField(max_length=40, unique=True)
    purchase = models.OneToOneField(Purchase, on_delete=models.PROTECT, related_name="receipt")
    issued_at = models.DateTimeField()
    seller = models.JSONField(help_text="Seller details at the time of issue.")

    email_status = models.CharField(max_length=10, choices=EmailStatus.choices, default=EmailStatus.PENDING, db_index=True)
    email_attempts = models.PositiveSmallIntegerField(default=0)
    email_last_attempt_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_last_error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.number


class ReceiptSequence(models.Model):
    """The last receipt number used in a financial year (locked while a number is taken)."""

    financial_year = models.CharField(max_length=7, unique=True, help_text='e.g. "2026-27".')
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.financial_year}: {self.last_number}"


class WebhookStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSED = "processed", "Processed"
    IGNORED = "ignored", "Ignored"
    FAILED = "failed", "Failed (Razorpay will retry)"


class WebhookEvent(models.Model):
    """One Razorpay webhook event (a retried delivery has the same event id)."""

    event_id = models.CharField(max_length=80, unique=True)
    event = models.CharField(max_length=60)
    razorpay_order_id = models.CharField(max_length=40, blank=True, db_index=True)
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.SET_NULL, related_name="webhook_events")
    status = models.CharField(max_length=10, choices=WebhookStatus.choices, default=WebhookStatus.RECEIVED)
    note = models.CharField(max_length=255, blank=True)
    deliveries = models.PositiveSmallIntegerField(default=1)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event} {self.event_id}"
