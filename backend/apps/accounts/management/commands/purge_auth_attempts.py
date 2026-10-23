from django.core.management.base import BaseCommand

from apps.accounts.password_auth import purge_old_attempts


class Command(BaseCommand):
    help = "Delete failed-login and password-reset records older than a day. Run daily (e.g. cron)."

    def handle(self, *args, **options):
        deleted = purge_old_attempts()
        self.stdout.write(f"Deleted {deleted} old sign-in attempt record(s).")
