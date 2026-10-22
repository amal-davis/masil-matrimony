from django.core.management.base import BaseCommand

from apps.accounts.otp import purge_expired_challenges


class Command(BaseCommand):
    help = "Delete SMS login challenges that expired more than a day ago. Run daily (e.g. cron)."

    def handle(self, *args, **options):
        deleted = purge_expired_challenges()
        self.stdout.write(f"Deleted {deleted} expired login challenge(s).")
