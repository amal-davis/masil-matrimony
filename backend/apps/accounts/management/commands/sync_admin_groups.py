"""
Create or update the staff groups used in the admin, with exactly the model
permissions listed below. Safe to run repeatedly; it never adds users to groups
and never touches superusers.

Give a staff account admin access by setting "Staff status" and adding it to one
of these groups in the admin (only superusers can do either).
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

VIEW_ALL = [
    "accounts.view_user",
    "profiles.view_profile",
    "profiles.view_profilephoto",
    "interactions.view_interest",
    "interactions.view_shortlist",
    "memberships.view_subscription",
    "notifications.view_notification",
    "enquiries.view_enquiry",
]

GROUPS = {
    # Can look at everything in the admin, change nothing.
    "Read-only reviewers": VIEW_ALL,
    # Approve or return profiles and photos (status changes go through the actions).
    "Profile moderators": [
        "accounts.view_user",
        "profiles.view_profile",
        "profiles.change_profile",
        "profiles.view_profilephoto",
        "profiles.change_profilephoto",
        "interactions.view_interest",
        "interactions.view_shortlist",
    ],
    # Record subscriptions after an offline payment and activate or cancel them.
    "Membership managers": [
        "accounts.view_user",
        "profiles.view_profile",
        "memberships.view_subscription",
        "memberships.add_subscription",
        "memberships.change_subscription",
    ],
    # Answer enquiries and look up members.
    "Support staff": [*VIEW_ALL, "enquiries.change_enquiry"],
}


class Command(BaseCommand):
    help = "Create or update the admin staff groups and their permissions."

    def handle(self, *args, **options):
        for name, perms in GROUPS.items():
            permissions = []
            for perm in perms:
                app_label, codename = perm.split(".")
                try:
                    permissions.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
                except Permission.DoesNotExist:
                    raise CommandError(f"Permission {perm} doesn't exist. Run migrate first.") from None
            group, created = Group.objects.get_or_create(name=name)
            group.permissions.set(permissions)
            self.stdout.write(f"{'Created' if created else 'Updated'} {name!r} ({len(permissions)} permissions)")
