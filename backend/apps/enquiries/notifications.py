"""
Email each new contact-form enquiry to the team's mailbox.

The address is settings.ENQUIRY_NOTIFICATION_EMAIL, or when that's empty the
address the site sends from (DEFAULT_FROM_EMAIL), so the message goes from and to
the same mailbox. Reply-To is the visitor, so answering it reaches them.

The enquiry is already saved before this runs: a failed email is logged and
the enquiry stays in the admin for staff to follow up.
"""
import logging
from email.utils import parseaddr

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from apps.notifications.mail import EmailError, send_email

from .models import Enquiry

logger = logging.getLogger(__name__)


def notification_address() -> str:
    """Where enquiries are emailed: ENQUIRY_NOTIFICATION_EMAIL, else the sender's own address."""
    return settings.ENQUIRY_NOTIFICATION_EMAIL or parseaddr(settings.DEFAULT_FROM_EMAIL)[1]


def notify_new_enquiry(enquiry: Enquiry, request=None) -> bool:
    """Email the enquiry's details to the team. Returns True once the mail server accepted it."""
    to = notification_address()
    if not to:
        logger.warning("Enquiry %s not emailed: no ENQUIRY_NOTIFICATION_EMAIL or DEFAULT_FROM_EMAIL", enquiry.public_id)
        return False

    path = reverse("admin:enquiries_enquiry_change", args=[enquiry.pk])
    if settings.API_PUBLIC_URL:
        admin_url = f"{settings.API_PUBLIC_URL.rstrip('/')}{path}"
    else:
        admin_url = request.build_absolute_uri(path) if request else ""
    body = render_to_string("emails/enquiry_received.txt", {"enquiry": enquiry, "admin_url": admin_url})

    try:
        # No personal details in the subject: send_email logs it. The short reference keeps each
        # enquiry in its own thread in the mailbox.
        send_email(to, f"New website enquiry {str(enquiry.public_id)[:8].upper()}", body, reply_to=enquiry.email)
    except EmailError as exc:
        # The id only: never the visitor's details or message.
        logger.error("Enquiry %s notification email failed: %s", enquiry.public_id, exc)
        return False
    return True
