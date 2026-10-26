"""
Payment receipts for paid membership purchases, issued by this application and
emailed through apps.notifications.mail. Razorpay's invoice API is not used, so
each purchase has exactly one document.

The document is a payment receipt, not a GST tax invoice: a tax invoice needs
details the business hasn't confirmed (GSTIN, legal name and address, place of
supply and the CGST/SGST or IGST split for the customer's state, SAC code).
The receipt shows the GST included in the amount paid and, when configured,
the seller's GSTIN. Seller details come only from settings (BILLING_*), copied
onto the receipt when it is issued; nothing is invented.

Numbers are <RECEIPT_NUMBER_PREFIX>/<financial year>/<6 digits>, e.g.
MM/2026-27/000001. The sequence row for the year is locked while a number is
taken, so simultaneous payments never share or skip a number.

Email: one receipt email per receipt, retried on failure (the
retry_receipt_emails command or the admin). "Sent" means the mail server
accepted the message, not that it reached the inbox. A failed email never
affects the payment or the membership.
"""
import logging
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.notifications.mail import EmailError, send_email

from .models import EmailStatus, Purchase, PurchaseStatus, Receipt, ReceiptSequence

logger = logging.getLogger(__name__)

SITE_NAME = "Massil Matrimony"


def financial_year(moment: datetime) -> str:
    """The Indian financial year (April to March) of a moment, in local time, e.g. "2026-27"."""
    local = timezone.localtime(moment)
    start = local.year if local.month >= 4 else local.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _next_number(issued_at: datetime) -> str:
    year = financial_year(issued_at)
    ReceiptSequence.objects.get_or_create(financial_year=year)
    sequence = ReceiptSequence.objects.select_for_update().get(financial_year=year)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])
    return f"{settings.RECEIPT_NUMBER_PREFIX}/{year}/{sequence.last_number:06d}"


def seller_details() -> dict:
    return {
        "brand": SITE_NAME,
        "legal_name": settings.BILLING_SELLER_NAME,
        "address": settings.BILLING_SELLER_ADDRESS,
        "gstin": settings.BILLING_SELLER_GSTIN,
        "email": settings.BILLING_CONTACT_EMAIL,
        "phone": settings.BILLING_CONTACT_PHONE,
    }


def issue_receipt(purchase: Purchase) -> Receipt:
    """The purchase's receipt, created on the first call. Only for paid purchases."""
    with transaction.atomic():
        locked = Purchase.objects.select_for_update().get(pk=purchase.pk)
        if locked.status != PurchaseStatus.PAID:
            raise ValueError("Receipts are issued only for paid purchases.")
        existing = Receipt.objects.filter(purchase=locked).first()
        if existing:
            return existing
        issued_at = timezone.now()
        return Receipt.objects.create(
            purchase=locked, number=_next_number(issued_at), issued_at=issued_at, seller=seller_details()
        )


def money(value) -> str:
    return f"{value:,.2f}"


def receipt_data(receipt: Receipt) -> dict:
    """Everything a receipt shows: the API response and the email use this."""
    purchase = receipt.purchase
    return {
        "id": str(receipt.public_id),
        "title": "Payment Receipt",
        "number": receipt.number,
        "issued_at": receipt.issued_at,
        "seller": receipt.seller,
        "customer": {"name": purchase.billing_name, "email": purchase.billing_email, "phone": purchase.billing_phone},
        "item": {
            "package": purchase.package_name,
            "description": f"Membership valid for {purchase.validity_months} months from activation.",
            "validity_months": purchase.validity_months,
            "starts_at": purchase.subscription.starts_at if purchase.subscription else None,
            "ends_at": purchase.subscription.ends_at if purchase.subscription else None,
        },
        "amounts": {
            "base": f"{purchase.base_amount:.2f}",
            "gst_rate": f"{purchase.gst_rate:.2f}",
            "gst": f"{purchase.gst_amount:.2f}",
            "total": f"{purchase.total_amount:.2f}",
            "currency": purchase.currency,
        },
        "payment": {
            "purchase_reference": purchase.reference,
            "razorpay_order_id": purchase.razorpay_order_id,
            "razorpay_payment_id": purchase.razorpay_payment_id,
            "paid_at": purchase.paid_at,
            "test_mode": purchase.mode == "test",
        },
    }


def _email_content(receipt: Receipt) -> tuple[str, str, str]:
    purchase = receipt.purchase
    context = {
        **receipt_data(receipt),
        "site_name": SITE_NAME,
        "site_url": settings.FRONTEND_URL,
        # The receipt page is reached by its random id, behind the member's sign-in.
        "receipt_url": f"{settings.FRONTEND_URL}/dashboard/membership/receipts/{receipt.public_id}",
        "greeting": f"Hello {purchase.billing_name}," if purchase.billing_name else "Hello,",
        "fmt": {
            "base": money(purchase.base_amount),
            "gst": money(purchase.gst_amount),
            "total": money(purchase.total_amount),
        },
    }
    subject = f"Payment receipt {receipt.number} – {SITE_NAME}"
    if purchase.mode == "test":
        subject = f"[TEST] {subject}"
    return (
        subject,
        render_to_string("emails/payment_receipt.txt", context),
        render_to_string("emails/payment_receipt.html", context),
    )


def send_receipt_email(receipt: Receipt, *, force: bool = False) -> bool:
    """
    Email the receipt to the purchase's billing address (the member's registered
    email when they paid). Returns True once the mail server has accepted it.
    `force` (staff resend) also sends after the automatic attempts ran out, or again after success.
    """
    with transaction.atomic():
        locked = Receipt.objects.select_for_update().select_related("purchase__subscription").get(pk=receipt.pk)
        if locked.email_status == EmailStatus.SENT and not force:
            return True
        if locked.email_attempts >= settings.RECEIPT_EMAIL_MAX_ATTEMPTS and not force:
            if locked.email_status != EmailStatus.GAVE_UP:
                locked.email_status = EmailStatus.GAVE_UP
                locked.save(update_fields=["email_status"])
            return False

        locked.email_attempts += 1
        locked.email_last_attempt_at = timezone.now()
        try:
            subject, text, html = _email_content(locked)
            send_email(locked.purchase.billing_email, subject, text, html=html)
        except EmailError as exc:
            exhausted = locked.email_attempts >= settings.RECEIPT_EMAIL_MAX_ATTEMPTS
            locked.email_status = EmailStatus.GAVE_UP if exhausted else EmailStatus.FAILED
            locked.email_last_error = str(exc)[:255]
            # The receipt number is logged, never the address.
            logger.error("Receipt %s email failed (attempt %d): %s", locked.number, locked.email_attempts, exc)
            sent = False
        else:
            locked.email_status = EmailStatus.SENT
            locked.email_sent_at = timezone.now()
            locked.email_last_error = ""
            logger.info("Receipt %s email accepted by the mail server", locked.number)
            sent = True
        locked.save(
            update_fields=["email_status", "email_attempts", "email_last_attempt_at", "email_sent_at", "email_last_error"]
        )
    return sent


def fulfil(purchase_id: int) -> None:
    """After a purchase is paid: issue its receipt and email it. Never raises; failures are retried later."""
    try:
        receipt = issue_receipt(Purchase.objects.get(pk=purchase_id))
        send_receipt_email(receipt)
    except Exception:  # noqa: BLE001 - the payment and membership are already committed
        logger.exception("Receipt for purchase %s not completed; retry_receipt_emails will retry", purchase_id)


def retry_pending_emails() -> tuple[int, int]:
    """Issue missing receipts for paid purchases and retry unsent emails. Returns (sent, failed)."""
    for purchase in Purchase.objects.filter(status=PurchaseStatus.PAID, receipt__isnull=True):
        issue_receipt(purchase)
    sent = failed = 0
    for receipt in Receipt.objects.filter(email_status__in=[EmailStatus.PENDING, EmailStatus.FAILED]):
        if send_receipt_email(receipt):
            sent += 1
        else:
            failed += 1
    return sent, failed
