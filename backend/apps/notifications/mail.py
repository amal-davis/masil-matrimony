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


def email_configured() -> bool:
    """True when emails with links back to the website can actually be delivered."""
    return (
        settings.EMAIL_PROVIDER in settings.EMAIL_BACKENDS
        and bool(settings.DEFAULT_FROM_EMAIL)
        and bool(settings.FRONTEND_URL)
    )


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email to one address. Raises EmailError if it wasn't accepted."""
    if not email_configured():
        raise EmailNotConfigured("EMAIL_PROVIDER, DEFAULT_FROM_EMAIL and FRONTEND_URL must be set.")
    try:
        send_mail(subject, body, None, [to], fail_silently=False)
    except (smtplib.SMTPException, OSError) as exc:
        # Never include the body: it may hold a password-reset link.
        raise EmailError(f"Email not sent: {exc.__class__.__name__}") from exc
    logger.info("Email %r accepted by %s", subject, settings.EMAIL_PROVIDER)
