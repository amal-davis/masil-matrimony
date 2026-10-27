"""
Razorpay webhooks (POST /api/v1/payments/razorpay/webhook/).

- The X-Razorpay-Signature header must be the HMAC-SHA256 of the raw request
  body with RAZORPAY_WEBHOOK_SECRET (not the API key secret). Anything else is
  rejected before the body is read as JSON.
- x-razorpay-event-id identifies an event across Razorpay's retries: an event
  already processed is acknowledged without doing anything again.
- The payload only says which order to look at. The decision is always made
  by apps.payments.services.reconcile from Razorpay's API, so events arriving
  twice, late or out of order (payment.captured before payment.authorized)
  can't move a purchase backwards or grant anything twice.
- If Razorpay's API can't be reached, the event is answered with 503 so Razorpay
  retries it.

Handled events: payment.authorized, payment.captured, payment.failed, order.paid,
and refund.created, refund.processed, payment.refunded (which record refunds).
Others are acknowledged and ignored. Nothing from the payload (which includes
the customer's email and phone) is logged.
"""
import hashlib
import json
import logging

from django.db import transaction
from django.utils import timezone

from . import razorpay_api
from .models import EventSource, Purchase, WebhookEvent, WebhookStatus
from .razorpay_api import RazorpayError
from .services import reconcile

logger = logging.getLogger(__name__)

HANDLED_EVENTS = {
    "payment.authorized", "payment.captured", "payment.failed", "order.paid",
    # Refunds made in Razorpay's dashboard: recorded on the purchase (the membership is left to staff).
    "refund.created", "refund.processed", "payment.refunded",
}


def _order_id(payload: dict) -> str:
    entities = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    payment = (entities.get("payment") or {}).get("entity") or {}
    order = (entities.get("order") or {}).get("entity") or {}
    return str(payment.get("order_id") or order.get("id") or "")[:40]


def handle(raw_body: bytes, signature: str, event_id: str) -> tuple[int, str]:
    """Process one webhook delivery. Returns (HTTP status, short note for the response)."""
    if not razorpay_api.webhook_configured():
        return 503, "Webhooks are not configured."
    if not razorpay_api.webhook_signature_valid(raw_body, signature):
        logger.warning("Razorpay webhook with an invalid signature rejected")
        return 400, "Invalid signature."
    try:
        payload = json.loads(raw_body)
    except ValueError:
        return 400, "Invalid JSON."
    if not isinstance(payload, dict):
        return 400, "Invalid payload."

    event = str(payload.get("event", ""))[:60]
    event_id = (event_id or "")[:80] or f"sha256:{hashlib.sha256(raw_body).hexdigest()[:72]}"
    order_id = _order_id(payload)

    with transaction.atomic():
        record, created = WebhookEvent.objects.select_for_update().get_or_create(
            event_id=event_id, defaults={"event": event, "razorpay_order_id": order_id}
        )
        if not created:
            record.deliveries += 1
            record.save(update_fields=["deliveries"])
            if record.status in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
                return 200, "Already processed."

    def finish(status, note, purchase=None):
        record.status = status
        record.note = note[:255]
        record.purchase = purchase or record.purchase
        record.processed_at = timezone.now()
        record.save(update_fields=["status", "note", "purchase", "processed_at"])

    if event not in HANDLED_EVENTS:
        finish(WebhookStatus.IGNORED, "Event not used.")
        return 200, "Ignored."
    purchase = Purchase.objects.filter(razorpay_order_id=order_id).first() if order_id else None
    if purchase is None:
        finish(WebhookStatus.IGNORED, "No purchase for this order.")
        return 200, "Ignored."
    try:
        purchase = reconcile(purchase, EventSource.WEBHOOK, None)
    except RazorpayError as exc:
        finish(WebhookStatus.FAILED, str(exc), purchase)
        logger.error("Webhook %s for purchase %s not processed: %s", event, purchase.reference, exc)
        return 503, "Try again later."
    finish(WebhookStatus.PROCESSED, f"Purchase is {purchase.status}.", purchase)
    return 200, "Processed."
