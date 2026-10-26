from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import AuthAttempt


class Command(BaseCommand):
    help = "Delete historical password sign-in attempt records older than a day. Run daily (e.g. cron)."

    def handle(self, *args, **options):
        deleted, _ = AuthAttempt.objects.filter(created_at__lt=timezone.now() - timedelta(days=1)).delete()
        self.stdout.write(f"Deleted {deleted} old sign-in attempt record(s).")
