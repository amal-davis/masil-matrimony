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
    "interactions.view_contactview",
    "memberships.view_membershippackage",
    "memberships.view_subscription",
    "memberships.view_assistancerequest",
    "notifications.view_notification",
    "enquiries.view_enquiry",
]

MATCHMAKING_CASE_WORK = [
    "memberships.view_assistancerequest",
    "memberships.change_assistancerequest",
    "memberships.view_assistancenote",
    "memberships.add_assistancenote",
    "memberships.change_assistancenote",
    "memberships.view_assistancefollowup",
    "memberships.add_assistancefollowup",
    "memberships.change_assistancefollowup",
    "memberships.view_assistancecandidate",
    "memberships.add_assistancecandidate",
    "memberships.change_assistancecandidate",
    "memberships.view_contactexchange",
    "memberships.add_contactexchange",
    "memberships.change_contactexchange",
    "memberships.view_contactconsent",
    "memberships.view_consultation",
    "memberships.add_consultation",
    "memberships.change_consultation",
    "memberships.view_familycontact",
    "memberships.add_familycontact",
    "memberships.change_familycontact",
    "memberships.view_familycoordination",
    "memberships.add_familycoordination",
]

# Automatic match recommendations (apps.matchmaking): look, and approve, dismiss or flag.
AUTO_MATCH_REVIEW = [
    "matchmaking.view_matchrecommendation",
    "matchmaking.view_pendingrecommendation",
    "matchmaking.view_mutualmatch",
    "matchmaking.view_matchrun",
    "matchmaking.review_matchrecommendation",
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
    # Record subscriptions after an offline payment and activate or cancel them, and edit
    # package copy. Fees, tax, validity and limits ("memberships.change_package_terms")
    # are deliberately in no group: only superusers change them.
    "Membership managers": [
        "accounts.view_user",
        "profiles.view_profile",
        "interactions.view_contactview",
        "memberships.view_membershippackage",
        "memberships.change_membershippackage",
        "memberships.view_subscription",
        "memberships.add_subscription",
        "memberships.change_subscription",
    ],
    # Matchmakers: work on the matchmaking cases assigned to them (Gold/Diamond requests and
    # Platinum service cases): notes, follow-ups, suggested profiles and consent-based contact
    # exchanges. They see only their own cases. No staff account is in this group until a
    # superuser adds one.
    "Matchmakers": [
        "accounts.view_user",
        "profiles.view_profile",
        "profiles.view_profilephoto",
        "interactions.view_interest",
        "interactions.view_shortlist",
        "memberships.view_subscription",
        *MATCHMAKING_CASE_WORK,
        *AUTO_MATCH_REVIEW,
    ],
    # Matchmaking managers: see every case and assign or reassign matchmakers.
    "Matchmaking managers": [
        "accounts.view_user",
        "profiles.view_profile",
        "profiles.view_profilephoto",
        "interactions.view_interest",
        "memberships.view_subscription",
        *MATCHMAKING_CASE_WORK,
        "memberships.assign_assistancerequest",
        *AUTO_MATCH_REVIEW,
        "matchmaking.generate_matchrecommendation",
    ],
    # Membership Purchases: payments, refunds as reported by Razorpay, revenue and CSV export.
    # They can ask Razorpay for a purchase's status (which is the only way a purchase becomes
    # paid) and resend receipts; nothing lets them mark anything paid or change an amount.
    "Finance staff": [
        "accounts.view_user",
        "profiles.view_profile",
        "memberships.view_subscription",
        "payments.view_purchase",
        "payments.change_purchase",
        "payments.view_purchase_financials",
        "payments.export_purchase",
        "payments.view_razorpaypayment",
        "payments.view_purchaseevent",
        "payments.view_receipt",
        "payments.change_receipt",
        "payments.view_webhookevent",
    ],
    # Answer enquiries and look up members.
    "Support staff": [*VIEW_ALL, "enquiries.change_enquiry"],
    # Write, publish and unpublish success stories on the website.
    "Content managers": [
        "website_content.view_successstory",
        "website_content.add_successstory",
        "website_content.change_successstory",
        "website_content.delete_successstory",
    ],
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
