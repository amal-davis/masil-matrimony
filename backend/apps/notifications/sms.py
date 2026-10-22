"""
Outgoing SMS. The provider is chosen by settings.SMS_PROVIDER; credentials come
only from environment variables.

    ""        not configured: sending is refused (the default)
    msg91     MSG91 Flow API with a DLT-approved template (India)
    console   DEVELOPMENT ONLY: writes the message to the server log
    locmem    TESTS ONLY: collects messages in `outbox`

production.py refuses to start with `console` or `locmem`, so a development
mock can never deliver (or reveal) codes for real accounts.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Messages sent with the "locmem" provider, newest last: [(phone_number, code), ...].
outbox: list[tuple[str, str]] = []


class SMSError(Exception):
    """The provider did not accept the message."""


class SMSNotConfigured(SMSError):
    """No SMS provider is configured, so nothing can be sent."""


def _mask(phone_number: str) -> str:
    return f"…{phone_number[-4:]}"


def _send_console(phone_number: str, code: str) -> None:
    # Development only (refused in production): lets a developer sign in without a gateway.
    logger.warning("[DEV SMS to %s] Your login code is %s", _mask(phone_number), code)


def _send_locmem(phone_number: str, code: str) -> None:
    outbox.append((phone_number, code))


def _send_msg91(phone_number: str, code: str) -> None:
    """
    MSG91 Flow API (v5). The message text is the DLT-approved template set up in
    the MSG91 panel; only the code is sent, as the template variable named by
    MSG91_OTP_VARIABLE. Verify the request format against MSG91's current API
    reference when configuring the account.
    """
    auth_key = settings.MSG91_AUTH_KEY
    template_id = settings.MSG91_OTP_TEMPLATE_ID
    if not auth_key or not template_id:
        raise SMSNotConfigured("MSG91_AUTH_KEY and MSG91_OTP_TEMPLATE_ID must be set.")

    body = {
        "template_id": template_id,
        "short_url": "0",
        # MSG91 takes the number with country code and without "+".
        "recipients": [{"mobiles": phone_number.lstrip("+"), settings.MSG91_OTP_VARIABLE: code}],
    }
    request = urllib.request.Request(
        "https://control.msg91.com/api/v5/flow",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"authkey": auth_key, "accept": "application/json", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.SMS_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read() or b"{}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        # The exception text can include the URL but never the code or auth key.
        raise SMSError(f"MSG91 request failed: {exc.__class__.__name__}") from exc

    if payload.get("type") != "success":
        raise SMSError(f"MSG91 rejected the message: {str(payload.get('message', ''))[:200]}")


_PROVIDERS = {
    "console": _send_console,
    "locmem": _send_locmem,
    "msg91": _send_msg91,
}


def sms_configured() -> bool:
    return settings.SMS_PROVIDER in _PROVIDERS


def send_otp_sms(phone_number: str, code: str) -> None:
    """Send a one-time code to an E.164 number. Raises SMSError if it wasn't accepted."""
    provider = settings.SMS_PROVIDER
    if not provider:
        raise SMSNotConfigured("SMS_PROVIDER is not set.")
    try:
        send = _PROVIDERS[provider]
    except KeyError:
        raise ImproperlyConfigured(f"Unknown SMS_PROVIDER {provider!r}.") from None
    send(phone_number, code)
    logger.info("OTP SMS accepted by %s for %s", provider, _mask(phone_number))
