"""
Callbacks used by the Django Unfold admin configuration (settings.UNFOLD).

Everything here runs per request for a signed-in staff user and respects
Django's model permissions: a staff member only sees the sidebar entries,
badges and dashboard figures for models they may view. Dashboard figures are
plain counts from the database; no member contact details are shown.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html

# --------------------------------------------------------------------------
# Branding and environment
# --------------------------------------------------------------------------


def site_icon(request):
    return static("brand/massil-monogram.png")


def site_url(request):
    """"View site" goes to the public website when its address is configured."""
    return settings.FRONTEND_URL or "/"


def environment_callback(request):
    """Badge in the admin header, so staff can't mistake a test copy for the live site."""
    name = settings.ADMIN_ENVIRONMENT_NAME
    colour = {"production": "danger", "staging": "warning"}.get(name.lower(), "info")
    return [name, colour]


# --------------------------------------------------------------------------
# Sidebar permissions (Unfold hides an entry when its callback returns False)
# --------------------------------------------------------------------------


def _can_view(perm):
    def check(request):
        return request.user.has_perm(perm)

    return check


can_view_users = _can_view("accounts.view_user")
can_view_profiles = _can_view("profiles.view_profile")
can_view_photos = _can_view("profiles.view_profilephoto")
can_view_interests = _can_view("interactions.view_interest")
can_view_shortlists = _can_view("interactions.view_shortlist")
can_view_subscriptions = _can_view("memberships.view_subscription")
can_view_packages = _can_view("memberships.view_membershippackage")
can_view_contact_views = _can_view("interactions.view_contactview")
can_view_enquiries = _can_view("enquiries.view_enquiry")
can_view_notifications = _can_view("notifications.view_notification")
can_view_groups = _can_view("auth.view_group")


def is_superuser(request):
    return request.user.is_superuser


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------


def _pending_counts(request):
    """Work waiting for staff, for the sidebar badges. Only for models the user may view."""
    from apps.enquiries.models import Enquiry
    from apps.memberships.models import Subscription, SubscriptionStatus
    from apps.profiles.choices import PhotoStatus, ProfileStatus
    from apps.profiles.models import Profile, ProfilePhoto

    user = request.user
    counts = {}
    if user.has_perm("profiles.view_profile"):
        counts["profiles"] = Profile.objects.filter(status=ProfileStatus.PENDING_REVIEW).count()
    if user.has_perm("profiles.view_profilephoto"):
        counts["photos"] = ProfilePhoto.objects.filter(status=PhotoStatus.PENDING).count()
    if user.has_perm("memberships.view_subscription"):
        counts["subscriptions"] = Subscription.objects.filter(status=SubscriptionStatus.PENDING).count()
    if user.has_perm("enquiries.view_enquiry"):
        counts["enquiries"] = Enquiry.objects.filter(status=Enquiry.Status.NEW).count()
    return counts


def sidebar_navigation(request):
    """
    The admin sidebar (settings.UNFOLD["SIDEBAR"]["navigation"]). Built per request
    so a badge appears only when something is waiting; Unfold hides each entry the
    user has no permission for.
    """
    pending = _pending_counts(request)

    def item(title, icon, url_name, permission, badge_key=None):
        entry = {"title": title, "icon": icon, "link": reverse(url_name), "permission": permission}
        if pending.get(badge_key):
            entry["badge"] = str(pending[badge_key])
        return entry

    return [
        {
            "title": "Overview",
            "items": [item("Dashboard", "dashboard", "admin:index", None)],
        },
        {
            "title": "Members & profiles",
            "separator": True,
            "items": [
                item("Accounts", "person", "admin:accounts_user_changelist", can_view_users),
                item("Profiles", "badge", "admin:profiles_profile_changelist", can_view_profiles, "profiles"),
                item("Profile photos", "photo_library", "admin:profiles_profilephoto_changelist", can_view_photos,
                     "photos"),
            ],
        },
        {
            "title": "Matchmaking",
            "separator": True,
            "items": [
                item("Interests", "favorite", "admin:interactions_interest_changelist", can_view_interests),
                item("Shortlists", "bookmark", "admin:interactions_shortlist_changelist", can_view_shortlists),
                item("Contact views", "contact_phone", "admin:interactions_contactview_changelist",
                     can_view_contact_views),
            ],
        },
        {
            "title": "Memberships",
            "separator": True,
            "items": [
                item("Packages", "sell", "admin:memberships_membershippackage_changelist", can_view_packages),
                item("Subscriptions", "workspace_premium", "admin:memberships_subscription_changelist",
                     can_view_subscriptions, "subscriptions"),
                item("Online purchases", "payments", "admin:payments_purchase_changelist",
                     _can_view("payments.view_purchase")),
                item("Receipts", "receipt_long", "admin:payments_receipt_changelist", _can_view("payments.view_receipt")),
                item("Razorpay webhooks", "webhook", "admin:payments_webhookevent_changelist",
                     _can_view("payments.view_webhookevent")),
            ],
        },
        {
            "title": "Website",
            "separator": True,
            "items": [
                item("Enquiries", "mail", "admin:enquiries_enquiry_changelist", can_view_enquiries, "enquiries"),
                item("Success stories", "favorite", "admin:website_content_successstory_changelist",
                     _can_view("website_content.view_successstory")),
            ],
        },
        {
            "title": "System",
            "separator": True,
            "collapsible": True,
            "items": [
                item("Notifications", "notifications", "admin:notifications_notification_changelist",
                     can_view_notifications),
                item("Staff groups", "group", "admin:auth_group_changelist", can_view_groups),
                item("Admin activity log", "history", "admin:admin_logentry_changelist", is_superuser),
            ],
        },
    ]


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------


def _stat(title, value, *, href=None, note=""):
    return {"title": title, "value": value, "href": href, "note": note}


def _date(value):
    return date_format(timezone.localtime(value), "j M Y") if value else "—"


def _link(url, text):
    return format_html('<a href="{}" class="font-medium text-primary-600 dark:text-primary-500">{}</a>', url, text)


def _panel(title, headers, rows, *, href=None, empty="Nothing here yet."):
    return {"title": title, "href": href, "table": {"headers": headers, "rows": rows}, "empty": empty}


def dashboard_callback(request, context):
    """
    Figures and recent activity for the admin index page, limited to the models
    the user may view. Lists show Matrimony IDs and dates, not member contact details.
    """
    from apps.accounts.roles import Role
    from apps.enquiries.models import Enquiry
    from apps.interactions.models import Interest, InterestStatus
    from apps.memberships.models import Subscription, SubscriptionStatus
    from apps.memberships.models import MembershipPackage
    from apps.profiles.choices import PhotoStatus, ProfileStatus
    from apps.profiles.models import Profile, ProfilePhoto

    user = request.user
    week_ago = timezone.now() - timedelta(days=7)
    stats, panels = [], []
    show_payments_notice = False

    if user.has_perm("accounts.view_user"):
        members = Role.MEMBER
        totals = get_user_model().objects.filter(role=members).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            new=Count("id", filter=Q(date_joined__gte=week_ago)),
        )
        users_url = f"{reverse('admin:accounts_user_changelist')}?role__exact={members}"
        stats += [
            _stat("Registered members", totals["total"], href=users_url),
            _stat("Active members", totals["active"], href=f"{users_url}&is_active__exact=1",
                  note="Accounts that are not deactivated"),
            _stat("New this week", totals["new"], href=users_url, note="Joined in the last 7 days"),
        ]

    if user.has_perm("profiles.view_profile"):
        pending_url = f"{reverse('admin:profiles_profile_changelist')}?status__exact={ProfileStatus.PENDING_REVIEW}"
        pending = Profile.objects.filter(status=ProfileStatus.PENDING_REVIEW)
        stats.append(_stat("Profiles awaiting review", pending.count(), href=pending_url))
        oldest = pending.order_by("submitted_at").only("pk", "profile_code", "submitted_at")[:5]
        panels.append(_panel(
            "Profiles awaiting review (oldest first)",
            ["Matrimony ID", "Submitted"],
            [[_link(reverse("admin:profiles_profile_change", args=[p.pk]), p.profile_code), _date(p.submitted_at)]
             for p in oldest],
            href=pending_url,
            empty="No profiles are waiting for review.",
        ))

    if user.has_perm("profiles.view_profilephoto"):
        photos_url = f"{reverse('admin:profiles_profilephoto_changelist')}?status__exact={PhotoStatus.PENDING}"
        stats.append(_stat("Photos awaiting review", ProfilePhoto.objects.filter(status=PhotoStatus.PENDING).count(),
                           href=photos_url))

    if user.has_perm("interactions.view_interest"):
        interests_url = f"{reverse('admin:interactions_interest_changelist')}?status__exact={InterestStatus.PENDING}"
        stats.append(_stat("Interests awaiting a reply",
                           Interest.objects.filter(status=InterestStatus.PENDING).count(), href=interests_url))

    if user.has_perm("memberships.view_subscription"):
        show_payments_notice = True
        subs_url = reverse("admin:memberships_subscription_changelist")
        current = Subscription.objects.current()
        stats += [
            _stat("Active memberships", current.count(), href=f"{subs_url}?status__exact={SubscriptionStatus.ACTIVE}"),
            _stat("Memberships to activate", Subscription.objects.filter(status=SubscriptionStatus.PENDING).count(),
                  href=f"{subs_url}?status__exact={SubscriptionStatus.PENDING}",
                  note="Recorded, waiting for payment confirmation"),
        ]
        per_plan = dict(current.order_by().values_list("plan_code").annotate(n=Count("id")))
        panels.append(_panel(
            "Membership packages",
            ["Package", "Validity", "Active members"],
            [[_link(f"{subs_url}?plan_code__exact={plan.code}", plan.name), f"{plan.validity_months} months",
              per_plan.get(plan.code, 0)] for plan in MembershipPackage.objects.exclude(validity_months=None)],
            href=subs_url,
        ))
        recent = Subscription.objects.select_related("user__profile").order_by("-created_at")[:5]
        panels.append(_panel(
            "Recent subscriptions",
            ["Matrimony ID", "Package", "Status", "Recorded"],
            [[_link(reverse("admin:memberships_subscription_change", args=[sub.pk]),
                    getattr(getattr(sub.user, "profile", None), "profile_code", "No profile")),
              sub.plan.name, sub.get_status_display(), _date(sub.created_at)] for sub in recent],
            href=subs_url,
            empty="No subscriptions have been recorded yet.",
        ))

    if user.has_perm("enquiries.view_enquiry"):
        enquiries_url = reverse("admin:enquiries_enquiry_changelist")
        stats.append(_stat("New enquiries", Enquiry.objects.filter(status=Enquiry.Status.NEW).count(),
                           href=f"{enquiries_url}?status__exact={Enquiry.Status.NEW}"))
        recent = Enquiry.objects.order_by("-created_at").only("pk", "status", "source", "created_at")[:5]
        panels.append(_panel(
            "Recent enquiries",
            ["Received", "Source", "Status"],
            [[_link(reverse("admin:enquiries_enquiry_change", args=[e.pk]), _date(e.created_at)),
              e.get_source_display(), e.get_status_display()] for e in recent],
            href=enquiries_url,
            empty="No enquiries yet.",
        ))

    context.update({
        "dashboard_stats": stats,
        "dashboard_panels": panels,
        # There is no payment gateway or payment model yet (apps/payments is a placeholder).
        "show_payments_notice": show_payments_notice,
    })
    return context
