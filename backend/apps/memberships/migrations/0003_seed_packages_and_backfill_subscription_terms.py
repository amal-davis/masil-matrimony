"""
Seed the six membership packages and store package terms on existing subscriptions.

- Packages that already exist are left as they are, so re-running never
  overwrites edits made in the admin.
- Diamond, Platinum and Royal keep the copy, prices and validity previously
  published on /our-packages (frontend/features/packages/packages.ts).
- Existing subscriptions get the validity and contact limit they were sold
  with (the values in the old apps/memberships/plans.py). Their fee is left
  empty for active and cancelled ones, because what each member actually paid
  offline was never recorded; pending ones get the current fee they'll pay.
"""
from decimal import Decimal

from django.db import migrations

TERMS_NOTE = "Benefits and contact access are subject to Maasil Matrimony.com's published terms and privacy policy."


def online_benefits(contact_limit, period, extras=()):
    period = f"the {period} membership period" if period else "the membership period"
    return [
        {"title": "Advanced Search"},
        {"title": "Unlimited Interest Sending"},
        {"title": "Personal Messaging"},
        {"title": "Photo Viewing"},
        {"title": "Profile Shortlist"},
        {"title": "Who Viewed My Profile?"},
        {"title": "Basic Match Suggestions"},
        {"title": "Verified Profile Badge for eligible profiles"},
        *({"title": title} for title in extras),
        {
            "title": f"Access to up to {contact_limit} member contact numbers during {period}, subject to "
            "applicable privacy settings, member consent, and company terms"
        },
    ]


PRIORITY_AND_ASSISTANCE = (
    "Priority Profile Visibility, subject to platform availability",
    "Dedicated Matchmaking Assistance, subject to service availability",
)

PACKAGES = [
    {
        "code": "free",
        "category": "online",
        "display_order": 10,
        "name": "Free Membership",
        "service_label": "Free Registration",
        "description": "Create your profile, browse members and send interests, at no cost.",
        "fee": Decimal("0"),
        "tax_treatment": "no_fee",
        "validity_months": None,
        "contact_view_limit": None,
        "outgoing_interest_limit": 15,
        "benefits": [
            {"title": "Profile Creation"},
            {"title": "Photo Upload"},
            {"title": "Basic Profile Search"},
            {
                "title": "View Other Profiles",
                "detail": "View other members' profiles and the basic details their privacy settings allow.",
            },
            {
                "title": "Send and Receive Interests",
                "detail": "Send up to 15 expressions of interest in total, and receive interests from other members.",
            },
            {
                "title": "Mobile Number Verification",
                "detail": "Mobile number verification by OTP, where the verification flow applies.",
            },
            {
                "title": "Basic Privacy and Contact Protection",
                "detail": "Your mobile number is never shown to free members, and only to paid members if you "
                "choose to share it.",
            },
            {
                "title": "Profile Review",
                "detail": "Your profile is reviewed by the Massil team before other members can see it, according "
                "to company policy.",
            },
        ],
        "terms_title": "Free Membership Terms",
        "terms_body": "Free membership has no fee. It includes up to 15 outgoing interests in total. Other members' "
        "mobile numbers are not visible on free membership: contact-number access needs an eligible paid "
        "membership and the other member's consent. What other members see of your profile depends on your "
        "privacy settings.",
        "cta_label": "Register Free",
    },
    {
        "code": "silver",
        "category": "online",
        "display_order": 20,
        "name": "Silver Membership",
        "service_label": "Online Membership",
        "description": "A three-month online membership with advanced search, unlimited interests and access to "
        "member contact numbers.",
        "fee": Decimal("5000"),
        "tax_treatment": "gst_extra",
        "validity_months": 3,
        "contact_view_limit": 40,
        "outgoing_interest_limit": None,
        "benefits": online_benefits(40, "three-month"),
        "terms_title": "Validity Terms",
        "terms_body": f"The Silver Membership is valid for three months from the activation date. {TERMS_NOTE}",
        "cta_label": "Choose Silver",
    },
    {
        "code": "gold",
        "category": "online",
        "display_order": 30,
        "name": "Gold Membership",
        "service_label": "Online Membership",
        "description": "A six-month online membership with wider contact access, priority visibility and "
        "matchmaking assistance.",
        "fee": Decimal("8000"),
        "tax_treatment": "gst_extra",
        "validity_months": 6,
        # Confirmed by the owner on 24 Oct 2026 (the supplied package text said both 100 and 70).
        "contact_view_limit": 100,
        "outgoing_interest_limit": None,
        "benefits": online_benefits(100, "six-month", PRIORITY_AND_ASSISTANCE),
        "terms_title": "Validity Terms",
        "terms_body": f"The Gold Membership is valid for six months from the activation date. {TERMS_NOTE}",
        "cta_label": "Choose Gold",
    },
    {
        "code": "diamond",
        "category": "online",
        "display_order": 40,
        "name": "Diamond Membership",
        "service_label": "Online Membership",
        "description": "An enhanced online membership for members who want additional profile discovery and "
        "communication features.",
        "fee": Decimal("12000"),
        "tax_treatment": "gst_extra",
        "validity_months": 12,
        "contact_view_limit": 100,
        "outgoing_interest_limit": None,
        "benefits": online_benefits(100, "", PRIORITY_AND_ASSISTANCE),
        "terms_title": "Validity Terms",
        "terms_body": f"The Diamond Membership is valid for twelve months from the activation date. {TERMS_NOTE}",
        "cta_label": "Choose Diamond",
    },
    {
        "code": "platinum",
        "category": "assisted",
        "display_order": 50,
        "name": "Platinum",
        "subtitle": "Assisted Matchmaking",
        "tagline": "Where Hearts Meet With Trust",
        "service_label": "Assisted Matchmaking",
        "description": "Personalised, staff-assisted matchmaking for members seeking dedicated guidance during "
        "their search.",
        "fee": Decimal("20000"),
        "fee_label": "Package fee",
        "tax_treatment": "gst_extra",
        "validity_months": 3,
        "contact_view_limit": None,
        "outgoing_interest_limit": None,
        "benefits": [
            {
                "title": "Free Online Registration",
                "detail": "Members receive free online registration and a personal member ID to access their "
                "profile and available platform features.",
            },
            {
                "title": "Dedicated Matchmaker",
                "detail": "A designated Massil matchmaking staff member assists the member throughout the service "
                "period.",
            },
            {
                "title": "Personalised Profile Search",
                "detail": "The matchmaker understands the member's preferences, searches for suitable profiles, and "
                "assists with shortlisting potential matches.",
            },
            {
                "title": "Interest Management",
                "detail": "Members can express interest through their online account. The matchmaker assists in "
                "coordinating mutual interest and follow-up.",
            },
            {
                "title": "Contact & Communication Coordination",
                "detail": "The assigned matchmaker coordinates contact exchange and communication with prospective "
                "matches and families, subject to consent and privacy requirements.",
            },
            {
                "title": "Follow-up Assistance",
                "detail": "The matchmaker assists with follow-ups and coordinates further discussions when both "
                "parties are interested.",
            },
            {
                "title": "Privacy & Confidentiality",
                "detail": "Member information is handled in accordance with Maasil Matrimony.com's privacy policy. "
                "Contact details are shared only with appropriate consent.",
            },
        ],
        "terms_title": "Service Terms",
        "terms_body": "The package is valid for three months from the activation date. The scope of staff "
        "assistance, service hours, profile shortlisting, and communication arrangements will be specified in the "
        "Platinum service agreement.",
        "cta_label": "Enquire About Platinum",
    },
    {
        "code": "royal",
        "category": "assisted",
        "display_order": 60,
        "name": "Royal",
        "subtitle": "Exclusive At-Home Matchmaking",
        "service_label": "At-Home Matchmaking",
        "description": "An exclusive, high-touch matchmaking service designed for busy professionals, "
        "entrepreneurs, business leaders, and families seeking a discreet, personalised experience.",
        "fee": Decimal("100000"),
        "fee_label": "Annual service fee",
        "tax_treatment": "gst_stated",
        "stated_gst_rate": Decimal("18"),
        "validity_months": 12,
        "contact_view_limit": None,
        "outgoing_interest_limit": None,
        "benefits": [
            {
                "title": "Exclusive Personalised Service",
                "detail": "Massil Royal is an exclusive, high-touch matchmaking service designed for busy "
                "professionals, business leaders, entrepreneurs, celebrities, and families seeking a discreet and "
                "personalised matchmaking experience.",
            },
            {
                "title": "At-Home Matchmaking",
                "detail": "A designated Massil matchmaking representative visits the member's residence at mutually "
                "agreed, convenient times to understand their preferences and present carefully shortlisted "
                "matrimonial profiles.",
            },
            {
                "title": "Personalised Profile Curation",
                "detail": "The Massil team identifies potential matches based on the member's preferences, family "
                "expectations, and agreed selection criteria. Members are not required to independently search "
                "through profiles online.",
            },
            {
                "title": "Dedicated Matchmaker",
                "detail": "A designated matchmaking representative coordinates profile selection, expressions of "
                "interest, communication, and follow-up throughout the service period.",
            },
            {
                "title": "Family Coordination",
                "detail": "With the consent of both parties, Massil assists in coordinating introductions, family "
                "discussions, and subsequent meetings.",
            },
            {
                "title": "Privacy & Confidentiality",
                "detail": "Member information, preferences, and family details are handled confidentially under the "
                "company's privacy policy. Profiles and contact details are shared only with appropriate permission.",
            },
        ],
        "terms_title": "Annual Service Validity",
        "terms_body": "The Royal package is valid for twelve months from the activation date. Home visits, service "
        "hours, travel arrangements, the number of shortlisted profiles, and other service limits will be "
        "specified in the signed service agreement.",
        "cta_label": "Enquire About Royal",
    },
]

# What subscriptions recorded before this migration were sold with (the old plans.py).
LEGACY_TERMS = {"diamond": (12, 100), "platinum": (3, None), "royal": (12, None)}


def forwards(apps, schema_editor):
    MembershipPackage = apps.get_model("memberships", "MembershipPackage")
    Subscription = apps.get_model("memberships", "Subscription")

    for data in PACKAGES:
        code = data["code"]
        MembershipPackage.objects.get_or_create(code=code, defaults={k: v for k, v in data.items() if k != "code"})

    fees = dict(MembershipPackage.objects.values_list("code", "fee"))
    for subscription in Subscription.objects.filter(validity_months=None):
        validity, contact_limit = LEGACY_TERMS[subscription.plan_code]
        subscription.validity_months = validity
        subscription.contact_view_limit = contact_limit
        if subscription.status == "pending":
            subscription.package_fee = fees[subscription.plan_code]
        subscription.save(update_fields=["validity_months", "contact_view_limit", "package_fee"])


def backwards(apps, schema_editor):
    # The package rows go with the table when 0002 is reversed; subscription terms likewise.
    pass


class Migration(migrations.Migration):
    dependencies = [("memberships", "0002_package_catalogue_and_subscription_terms")]

    operations = [migrations.RunPython(forwards, backwards)]
