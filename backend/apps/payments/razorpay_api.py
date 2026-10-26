"""
The Razorpay calls this project makes, per Razorpay's API reference:

- Create an order:   POST https://api.razorpay.com/v1/orders
                     {"amount": <paise, integer>, "currency": "INR", "receipt": <= 40 chars, "notes": {...}}
- Payments of order: GET  https://api.razorpay.com/v1/orders/<order_id>/payments
                     -> {"entity": "collection", "count": n, "items": [payment, ...]}
  Payment states: created, authorized, captured, refunded, failed.

Both use HTTP Basic auth with the key id and key secret.

Signatures (HMAC-SHA256, hex digest, compared in constant time):
- Checkout: hmac(key_secret, "<order_id>|<razorpay_payment_id>"), using the order id
  stored on this server, compared with razorpay_signature.
- Webhooks: hmac(webhook_secret, <raw request body>), compared with the
  X-Razorpay-Signature header. The body must not be parsed or re-serialised first.

The key secret and webhook secret never leave this module's requests or appear in
logs or exceptions.
"""
import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    """Razorpay didn't give a usable answer. The message never contains credentials."""


class RazorpayNotConfigured(RazorpayError):
    pass


def configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def webhook_configured() -> bool:
    return bool(settings.RAZORPAY_WEBHOOK_SECRET)


def _request(method: str, path: str, body: dict | None = None) -> dict:
    if not configured():
        raise RazorpayNotConfigured("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are not set.")
    token = base64.b64encode(f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()).decode()
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.RAZORPAY_TIMEOUT_SECONDS) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        # Razorpay's error body: {"error": {"code": ..., "description": ...}}. Never the request headers.
        try:
            error = json.loads(exc.read() or b"{}").get("error", {})
        except ValueError:
            error = {}
        description = str(error.get("description", ""))[:200]
        raise RazorpayError(f"Razorpay answered HTTP {exc.code} {error.get('code', '')}: {description}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RazorpayError(f"Razorpay request failed: {exc.__class__.__name__}") from None


def create_order(amount_subunits: int, currency: str, receipt: str, notes: dict) -> dict:
    order = _request(
        "POST", "/orders", {"amount": amount_subunits, "currency": currency, "receipt": receipt, "notes": notes}
    )
    if not isinstance(order, dict) or not str(order.get("id", "")).startswith("order_"):
        raise RazorpayError("Razorpay returned an order without an id.")
    if order.get("amount") != amount_subunits or order.get("currency") != currency:
        raise RazorpayError("Razorpay returned an order for a different amount or currency.")
    return order


def order_payments(order_id: str) -> list[dict]:
    data = _request("GET", f"/orders/{urllib.parse.quote(order_id, safe='')}/payments")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise RazorpayError("Razorpay returned an unexpected payments list.")
    return [item for item in items if isinstance(item, dict)]


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def checkout_signature_valid(order_id: str, payment_id: str, signature: str) -> bool:
    if not (settings.RAZORPAY_KEY_SECRET and order_id and payment_id and signature):
        return False
    expected = _hmac_hex(settings.RAZORPAY_KEY_SECRET, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature)


def webhook_signature_valid(raw_body: bytes, signature: str) -> bool:
    if not (settings.RAZORPAY_WEBHOOK_SECRET and signature):
        return False
    return hmac.compare_digest(_hmac_hex(settings.RAZORPAY_WEBHOOK_SECRET, raw_body), signature)
