"""
Remove every member account and everything that belongs to them, for clearing
test registrations from a development database. Then restart the id counters
of the tables that are left empty, so the next records start at id 1.

    manage.py clear_member_data             # dry run: what would be deleted (nothing changes)
    manage.py clear_member_data --confirm   # delete

Deleted: accounts with the "member" role (never staff or superusers) and their
profiles, photos (rows and image files), partner preferences, interests,
shortlists, contact and profile views, messages, notifications, memberships,
purchases and their payment records, receipts, matchmaking recommendations
and cases, sign-in tokens, plus the OTP and sign-in attempt records used while
registering. Everything else stays: staff accounts and groups, packages,
success stories, enquiries, admin history and settings.

An id counter can't go below a row that stays (e.g. the superuser's id in the
accounts table): there it continues after the highest remaining id.

Refused when DEBUG is off (production) unless --allow-production is given.
Take a database backup first.
"""
from collections import Counter

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import ProtectedError, RestrictedError

from apps.accounts.models import AuthAttempt, OTPNumberLock, PhoneOTPChallenge, User
from apps.accounts.roles import Role


class Command(BaseCommand):
    help = "Delete all member accounts and their data (keeps staff and site content); restart emptied id counters."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually delete. Without it, nothing changes.")
        parser.add_argument("--allow-production", action="store_true", help="Run even with DEBUG off.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("DEBUG is off: this looks like production. Refusing (see --allow-production).")
        members = User.objects.filter(role=Role.MEMBER, is_staff=False, is_superuser=False)
        member_count = members.count()

        from apps.profiles.models import ProfilePhoto

        photo_files = list(ProfilePhoto.objects.filter(profile__user__in=members).values_list("image", flat=True))
        counts = Counter()
        with transaction.atomic():
            self._delete_all(members, counts)
            if not options["confirm"]:
                transaction.set_rollback(True)

        self.stdout.write(f"{'Deleted' if options['confirm'] else 'Would delete'} {member_count} member account(s):")
        for label, number in sorted(counts.items()):
            if number:
                self.stdout.write(f"  {label}: {number}")
        if not options["confirm"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing was changed. Back up the database, then add --confirm."))
            return

        removed = self._delete_files(photo_files)
        self.stdout.write(f"Removed {removed} photo file(s) and {self._remove_empty_photo_folders()} empty folder(s).")
        for table, next_id in self._restart_counters([label for label, n in counts.items() if n]):
            self.stdout.write(f"  next id in {table}: {next_id}")
        self.stdout.write(self.style.SUCCESS("Done."))

    # --- Deleting -------------------------------------------------------------------

    def _delete_all(self, members, counts):
        from apps.payments.models import Receipt, ReceiptSequence
        from apps.profiles.models import Profile

        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        # Sign-in tokens are kept (user set to null) when an account goes: remove the members' and any
        # left over from accounts deleted earlier.
        self._purge(OutstandingToken.objects.filter(user__in=members), counts)
        self._purge(OutstandingToken.objects.filter(user__isnull=True), counts)
        self._purge(Profile.objects.filter(user__in=members), counts)
        self._purge(User.objects.filter(pk__in=list(members.values_list("pk", flat=True))), counts)
        # Registration and sign-in records (codes, per-number locks, old attempt counters).
        for model in (PhoneOTPChallenge, OTPNumberLock, AuthAttempt):
            self._purge(model.objects.all(), counts)
        if not Receipt.objects.exists():
            self._purge(ReceiptSequence.objects.all(), counts)  # receipt numbers start again at 000001

    def _purge(self, queryset, counts):
        """Delete, first removing whatever protects these rows (always more of the members' data)."""
        while True:
            try:
                with transaction.atomic():
                    _, per_model = queryset.delete()
                counts.update(per_model)
                return
            except (ProtectedError, RestrictedError) as error:
                blockers = getattr(error, "protected_objects", None) or getattr(error, "restricted_objects", None)
                by_model = {}
                for obj in blockers:
                    if isinstance(obj, User) and not obj.role == Role.MEMBER:
                        raise CommandError(f"A staff account ({obj.pk}) is linked to member data; nothing was deleted.")
                    by_model.setdefault(type(obj), set()).add(obj.pk)
                for model, pks in by_model.items():
                    self._purge(model.objects.filter(pk__in=pks), counts)

    def _delete_files(self, names) -> int:
        from apps.profiles.models import ProfilePhoto

        storage = ProfilePhoto._meta.get_field("image").storage
        removed = 0
        for name in names:
            if name and storage.exists(name):
                storage.delete(name)
                removed += 1
        return removed

    def _remove_empty_photo_folders(self) -> int:
        """Per-profile photo folders left empty (local file storage only)."""
        from pathlib import Path

        from apps.profiles.models import ProfilePhoto

        storage = ProfilePhoto._meta.get_field("image").storage
        try:
            root = Path(storage.path("profile-photos"))
        except NotImplementedError:
            return 0
        removed = 0
        for folder in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
                removed += 1
        return removed

    # --- Id counters ------------------------------------------------------------------

    def _restart_counters(self, labels):
        """Restart AUTO_INCREMENT: 1 for empty tables, highest id + 1 otherwise (the server's own rule)."""
        tables = sorted({apps.get_model(label)._meta.db_table for label in labels} | {
            PhoneOTPChallenge._meta.db_table, OTPNumberLock._meta.db_table, AuthAttempt._meta.db_table,
        })
        results = []
        with connection.cursor() as cursor:
            for table in tables:
                quoted = connection.ops.quote_name(table)
                if connection.vendor == "mysql":
                    cursor.execute(f"ALTER TABLE {quoted} AUTO_INCREMENT = 1")
                elif connection.vendor == "sqlite":
                    cursor.execute("UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(rowid), 0) FROM "
                                   f"{quoted}) WHERE name = %s", [table])
                else:
                    continue
                cursor.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {quoted}")
                results.append((table, cursor.fetchone()[0]))
        return results
