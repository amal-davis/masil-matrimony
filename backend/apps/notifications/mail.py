"""
Outgoing email. The provider is chosen by settings.EMAIL_PROVIDER; SMTP
credentials come only from environment variables.

    ""        not configured: sending is refused (the default)
    smtp      any SMTP server or transactional email service (EMAIL_HOST etc.)
    console   DEVELOPMENT ONLY: prints the message to the server console
    locmem    TESTS ONLY: collects messages in django.core.mail.outbox

production.py refuses to start with `console` or `locmem`, so a development
mock can never reveal password-reset links for real accounts.
"""
import logging
import smtplib

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class EmailError(Exception):
    """The message could not be handed to the mail server."""


class EmailNotConfigured(EmailError):
    """No email provider is configured, so nothing can be sent."""


def delivery_mode() -> str:
    """
    How email is handled right now: "smtp" (really sent), "console" (printed by the
    API server, development only), "locmem" (tests), or "" (not configured).
    Lets the website say honestly where a verification email went.
    """
    return settings.EMAIL_PROVIDER if settings.EMAIL_PROVIDER in settings.EMAIL_BACKENDS else ""


def describe_failure(exc: BaseException) -> str:
    """
    What went wrong, for logs and the send_test_email command: the kind of failure
    and which setting to check. Never the server's reply, which can echo the username.
    """
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "the SMTP server rejected the login: check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD "
            "(for Gmail, a 16-character App Password, not the account password)"
        )
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "the SMTP server refused the sender: DEFAULT_FROM_EMAIL must be an address this account may send as"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "the SMTP server refused the recipient address"
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return "the SMTP server doesn't support a requested feature: check EMAIL_USE_TLS / EMAIL_USE_SSL and EMAIL_PORT"
    if isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError)):
        return (
            f"couldn't talk to {settings.EMAIL_HOST or '(EMAIL_HOST not set)'}:{settings.EMAIL_PORT}: check "
            "EMAIL_HOST, EMAIL_PORT (587 with EMAIL_USE_TLS=True, or 465 with EMAIL_USE_SSL=True) and the network"
        )
    if isinstance(exc, OSError):
        return f"network error reaching {settings.EMAIL_HOST or '(EMAIL_HOST not set)'}:{settings.EMAIL_PORT}"
    return exc.__class__.__name__


def email_configured() -> bool:
    """True when emails with links back to the website can actually be delivered."""
    return (
        settings.EMAIL_PROVIDER in settings.EMAIL_BACKENDS
        and bool(settings.DEFAULT_FROM_EMAIL)
        and bool(settings.FRONTEND_URL)
    )


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    """
    Send an email to one address: plain text, plus an HTML alternative when `html`
    is given. Raises EmailError if it wasn't accepted.
    """
    if not email_configured():
        raise EmailNotConfigured("EMAIL_PROVIDER, DEFAULT_FROM_EMAIL and FRONTEND_URL must be set.")
    try:
        send_mail(subject, body, None, [to], fail_silently=False, html_message=html)
    except (smtplib.SMTPException, OSError) as exc:
        # Never include the body (it may hold a password-reset or verification link) or the
        # server's reply (it can echo credentials): describe_failure names the setting to check.
        raise EmailError(f"Email not sent ({exc.__class__.__name__}): {describe_failure(exc)}") from exc
    logger.info("Email %r accepted by %s", subject, settings.EMAIL_PROVIDER)
