from django.core.management.base import BaseCommand

from apps.accounts.otp import purge_expired_challenges


class Command(BaseCommand):
    help = (
        "Delete SMS code challenges (and the details of registrations never verified) "
        "that expired more than a day ago. Run daily (e.g. cron)."
    )

    def handle(self, *args, **options):
        deleted = purge_expired_challenges()
        self.stdout.write(f"Deleted {deleted} expired code challenge(s).")
