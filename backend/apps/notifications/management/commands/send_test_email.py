"""
Check the outgoing-email settings and send one real test message.

    python manage.py send_test_email you@example.com

Reports which settings are missing (never their values; the password is only
reported as set or not set), then hands one message to the configured server and
says whether it was accepted. "Accepted" means the SMTP server took the message;
check the inbox (and spam folder) to confirm delivery.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from apps.notifications.mail import EmailError, delivery_mode, email_configured, send_email


class Command(BaseCommand):
    help = "Check the email settings and send a test message to one address."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Address to send the test message to.")

    def handle(self, *args, to, **options):
        try:
            validate_email(to)
        except ValidationError:
            raise CommandError("Give a valid email address to send the test message to.") from None

        mode = delivery_mode()
        self.stdout.write(f"EMAIL_PROVIDER: {mode or '(not set)'}")
        problems = []
        if not mode:
            problems.append("EMAIL_PROVIDER must be 'smtp' (or 'console' to print emails while developing).")
        if mode == "smtp":
            for name in ("EMAIL_HOST", "EMAIL_HOST_USER"):
                value = getattr(settings, name)
                self.stdout.write(f"{name}: {'set' if value else 'NOT SET'}")
                if not value:
                    problems.append(f"{name} is empty.")
            self.stdout.write(f"EMAIL_PORT: {settings.EMAIL_PORT}  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}  "
                              f"EMAIL_USE_SSL: {settings.EMAIL_USE_SSL}")
            self.stdout.write(f"EMAIL_HOST_PASSWORD: {'set' if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
            if not settings.EMAIL_HOST_PASSWORD:
                problems.append("EMAIL_HOST_PASSWORD is empty (for Gmail, create an App Password).")
            if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
                problems.append("Set only one of EMAIL_USE_TLS (port 587) and EMAIL_USE_SSL (port 465).")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {'set' if settings.DEFAULT_FROM_EMAIL else 'NOT SET'}")
        self.stdout.write(f"FRONTEND_URL: {settings.FRONTEND_URL or 'NOT SET'}")
        if not settings.DEFAULT_FROM_EMAIL:
            problems.append("DEFAULT_FROM_EMAIL is empty.")
        if not settings.FRONTEND_URL:
            problems.append("FRONTEND_URL is empty, so emailed links would have nowhere to point.")
        if problems or not email_configured():
            raise CommandError("Email isn't fully configured:\n- " + "\n- ".join(problems or ["see above"]))

        try:
            send_email(
                to,
                "Massil Matrimony test email",
                "This is a test message from the Massil Matrimony API, sent by `manage.py send_test_email`.\n",
            )
        except EmailError as exc:
            raise CommandError(str(exc)) from None

        if mode == "console":
            self.stdout.write(self.style.WARNING(
                "Printed above by the console backend; NOT delivered. Set EMAIL_PROVIDER=smtp to send real email."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Accepted by {settings.EMAIL_HOST}. Check the inbox (and spam folder) of the address you gave."
            ))
