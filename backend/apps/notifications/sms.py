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
    # ASCII, so Windows consoles and log files show it as written.
    return f"***{phone_number[-4:]}"


def _send_console(phone_number: str, code: str) -> None:
    # Development only (refused in production): lets a developer register and sign in without a
    # gateway. A banner, so the code stands out among the request lines in the runserver terminal.
    minutes = max(1, settings.OTP_TTL_SECONDS // 60)
    logger.warning(
        "\n"
        "============================================================\n"
        "  DEV SMS (not sent: SMS_PROVIDER=console)\n"
        "  To:   %s\n"
        "  Your Massil Matrimony verification code is %s\n"
        "  Valid for %d minutes.\n"
        "============================================================",
        _mask(phone_number), code, minutes,
    )


def _send_locmem(phone_number: str, code: str) -> None:
    outbox.append((phone_number, code))


def _msg91_error_message(payload) -> str:
    message = payload.get("message", "") if isinstance(payload, dict) else ""
    # Bounded, and only MSG91's own text: never the request, which holds the code.
    return str(message)[:200]


def _send_msg91(phone_number: str, code: str) -> None:
    """
    MSG91 Flow API (v5): POST https://control.msg91.com/api/v5/flow with the
    `authkey` header and {"template_id", "short_url", "recipients": [{"mobiles":
    "<country code + number, no +>", "<variable>": "<value>"}]}; MSG91 answers
    {"type": "success", "message": "<request id>"} when it accepts the message,
    or {"type": "error", "message": "..."}. See MSG91's API reference (SMS >
    Send SMS) and the "Sample Codes" for the template in the MSG91 panel.

    The message text is the DLT-approved template set up in the MSG91 panel
    (SMS > Templates); only the code is sent, as the template variable named by
    MSG91_OTP_VARIABLE. "Accepted" means MSG91 took the message for delivery;
    whether it reached the handset shows in MSG91's delivery reports.
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
    except urllib.error.HTTPError as exc:
        # 401/403: wrong auth key or IP not whitelisted; 4xx: bad template or number; 5xx: MSG91 trouble.
        try:
            detail = _msg91_error_message(json.loads(exc.read() or b"{}"))
        except ValueError:
            detail = ""
        raise SMSError(f"MSG91 answered HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        # Network failure, timeout or a reply that isn't JSON. Never includes the code or auth key.
        raise SMSError(f"MSG91 request failed: {exc.__class__.__name__}") from exc

    if not isinstance(payload, dict) or payload.get("type") != "success":
        raise SMSError(f"MSG91 rejected the message: {_msg91_error_message(payload)}")


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
