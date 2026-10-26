from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.phone import normalize_mobile_number
from apps.accounts.roles import Role


class Command(BaseCommand):
    help = (
        "Read-only report on member accounts and SMS sign-in: who can sign in with their mobile "
        "number, and who needs staff help first. Changes nothing. Lists accounts by public id only."
    )

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="List the public ids of accounts needing attention.")

    def handle(self, *args, **options):
        members = User.objects.filter(role=Role.MEMBER)
        no_number = list(members.filter(phone_number=None).values_list("public_id", flat=True))
        unsupported = []
        for public_id, number in members.exclude(phone_number=None).values_list("public_id", "phone_number"):
            try:
                normalize_mobile_number(number)
            except ValidationError:
                unsupported.append(public_id)

        self.stdout.write(f"Members: {members.count()}")
        self.stdout.write(f"  mobile number verified:            {members.exclude(phone_verified_at=None).count()}")
        self.stdout.write(
            "  number on file, not yet verified:  "
            f"{members.filter(phone_verified_at=None).exclude(phone_number=None).count()}"
            "  (verified automatically at their first SMS sign-in)"
        )
        self.stdout.write(f"  no mobile number:                  {len(no_number)}  (can't sign in; staff must add one)")
        self.stdout.write(
            f"  number SMS codes can't be sent to: {len(unsupported)}"
            "  (not a mobile number in SMS_ALLOWED_COUNTRY_CODES; staff must correct it)"
        )
        no_email = members.filter(email=None).count()
        self.stdout.write(
            f"  no email address:                  {no_email}  (can't pay online until they add one in Account Settings)"
        )
        if options["list"]:
            for label, ids in (("No mobile number", no_number), ("Unsupported number", unsupported)):
                for public_id in ids:
                    self.stdout.write(f"{label}: {public_id}")
