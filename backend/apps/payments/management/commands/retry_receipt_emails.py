from django.core.management.base import BaseCommand

from apps.payments.receipts import retry_pending_emails


class Command(BaseCommand):
    help = (
        "Issue receipts missing for paid purchases and retry receipt emails that haven't been accepted by the "
        "mail server (up to RECEIPT_EMAIL_MAX_ATTEMPTS each). Safe to run any time; run it every few minutes (cron)."
    )

    def handle(self, *args, **options):
        sent, failed = retry_pending_emails()
        self.stdout.write(f"Receipt emails accepted: {sent}; still failing: {failed}.")
