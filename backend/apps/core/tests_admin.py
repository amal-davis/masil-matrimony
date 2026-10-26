from io import StringIO

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.memberships.models import Subscription, SubscriptionStatus
from apps.profiles.choices import ProfileStatus
from apps.profiles.models import Profile, ProfilePhoto
from apps.profiles.test_utils import PASSWORD, make_profile, make_user

CHANGELISTS = [
    "admin:accounts_user_changelist",
    "admin:profiles_profile_changelist",
    "admin:profiles_profilephoto_changelist",
    "admin:interactions_interest_changelist",
    "admin:interactions_shortlist_changelist",
    "admin:memberships_subscription_changelist",
    "admin:notifications_notification_changelist",
    "admin:enquiries_enquiry_changelist",
    "admin:auth_group_changelist",
    "admin:admin_logentry_changelist",
]


def make_staff(email, *groups):
    user = User.objects.create_user(email=email, password=PASSWORD, role=Role.ADMIN, is_staff=True)
    if groups:
        call_command("sync_admin_groups", stdout=StringIO())
        user.groups.set(Group.objects.filter(name__in=groups))
    return user


class AdminAccessTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(email="root@example.com", password=PASSWORD)

    def test_login_page_uses_unfold_branding(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Massil Matrimony")
        self.assertTemplateUsed(response, "unfold/layouts/unauthenticated.html")

    def test_anonymous_and_member_accounts_are_sent_to_login(self):
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")
        member = make_user()
        self.client.force_login(member)
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")

    def test_superuser_can_sign_in_with_email_and_password(self):
        response = self.client.post(
            reverse("admin:login"), {"username": "root@example.com", "password": PASSWORD, "next": "/admin/"}
        )
        self.assertRedirects(response, "/admin/")

    def test_every_section_and_search_loads(self):
        make_profile()
        self.client.force_login(self.superuser)
        for name in CHANGELISTS:
            url = reverse(name)
            self.assertEqual(self.client.get(url).status_code, 200, name)
            self.assertEqual(self.client.get(url, {"q": "MM"}).status_code, 200, f"{name} search")
        self.assertEqual(self.client.get(reverse("admin:accounts_user_add")).status_code, 200)

    def test_member_found_by_matrimony_id(self):
        profile = make_profile()
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:accounts_user_changelist"), {"q": profile.profile_code})
        self.assertContains(response, profile.user.email)

    def test_token_tables_are_not_in_the_admin(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get("/admin/token_blacklist/outstandingtoken/").status_code, 404)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(email="root@example.com", password=PASSWORD)

    def stats(self, response):
        return {stat["title"]: stat["value"] for stat in response.context["dashboard_stats"]}

    def test_empty_database(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        stats = self.stats(response)
        self.assertEqual(stats["Registered members"], 0)
        self.assertEqual(stats["Active memberships"], 0)
        self.assertContains(response, "No profiles are waiting for review.")
        self.assertContains(response, "no payment gateway is connected yet")

    def test_figures_come_from_the_database(self):
        make_profile(status=ProfileStatus.PENDING_REVIEW)
        make_profile()
        inactive = make_user(is_active=False)
        Subscription.objects.create(user=inactive, plan_code="diamond")
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        stats = self.stats(response)
        self.assertEqual(stats["Registered members"], 3)
        self.assertEqual(stats["Active members"], 2)
        self.assertEqual(stats["Profiles awaiting review"], 1)
        self.assertEqual(stats["Memberships to activate"], 1)
        # Dashboard lists show Matrimony IDs, never member emails or phone numbers.
        self.assertNotContains(response, inactive.email)
        self.assertNotContains(response, inactive.phone_number)

    def test_staff_without_permissions_see_no_figures(self):
        staff = make_staff("staff@example.com")
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"], [])
        self.assertEqual(self.client.get(reverse("admin:profiles_profile_changelist")).status_code, 403)


class AdminPermissionTests(TestCase):
    def test_read_only_group_can_view_but_not_change(self):
        profile = make_profile()
        staff = make_staff("reviewer@example.com", "Read-only reviewers")
        self.client.force_login(staff)
        change_url = reverse("admin:profiles_profile_change", args=[profile.pk])
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.post(change_url, {}).status_code, 403)
        response = self.client.get(reverse("admin:profiles_profile_changelist"))
        # No actions at all (approve, request changes, delete) for a view-only user.
        self.assertIsNone(response.context["action_form"])
        self.assertEqual(self.client.get(reverse("admin:admin_logentry_changelist")).status_code, 403)

    def test_staff_cannot_grant_privileges_or_edit_superusers(self):
        root = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        staff = make_staff("support@example.com")
        staff.user_permissions.add(*Permission.objects.filter(codename__in=["view_user", "change_user"]))
        self.client.force_login(staff)
        own = self.client.get(reverse("admin:accounts_user_change", args=[staff.pk]))
        self.assertEqual(own.status_code, 200)
        self.assertIn("is_superuser", own.context["adminform"].readonly_fields)
        root_url = reverse("admin:accounts_user_change", args=[root.pk])
        self.assertEqual(self.client.post(root_url, {"email": "taken@example.com"}).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("admin:auth_user_password_change", args=[root.pk])).status_code, 403
        )

    def test_profile_and_photo_status_are_read_only(self):
        for model in (Profile, ProfilePhoto):
            self.assertIn("status", admin.site._registry[model].readonly_fields)


class SubscriptionAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        self.subscription = Subscription.objects.create(user=make_user(), plan_code="diamond")
        self.url = reverse("admin:memberships_subscription_changelist")
        self.client.force_login(self.superuser)

    def run_action(self, action, **extra):
        return self.client.post(self.url, {"action": action, "_selected_action": [self.subscription.pk], **extra})

    def test_cancel_asks_for_confirmation_first(self):
        response = self.run_action("cancel")
        self.assertTemplateUsed(response, "admin/memberships/subscription/cancel_confirmation.html")
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, SubscriptionStatus.PENDING)

        self.run_action("cancel", confirmed="yes")
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, SubscriptionStatus.CANCELLED)
        self.assertTrue(LogEntry.objects.filter(object_id=str(self.subscription.pk)).exists())

    def test_activation_is_logged(self):
        self.run_action("activate")
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, SubscriptionStatus.ACTIVE)
        self.assertTrue(LogEntry.objects.filter(change_message__contains="Activated").exists())


class SyncAdminGroupsTests(TestCase):
    def test_creates_groups_and_is_idempotent(self):
        call_command("sync_admin_groups", stdout=StringIO())
        call_command("sync_admin_groups", stdout=StringIO())
        reviewers = Group.objects.get(name="Read-only reviewers")
        self.assertTrue(reviewers.permissions.exists())
        self.assertFalse(reviewers.permissions.exclude(codename__startswith="view_").exists())
        self.assertEqual(Group.objects.count(), 5)
        content = Group.objects.get(name="Content managers")
        self.assertEqual(
            set(content.permissions.values_list("codename", flat=True)),
            {"view_successstory", "add_successstory", "change_successstory", "delete_successstory"},
        )


class SidebarTests(TestCase):
    def navigation(self, user):
        from django.test import RequestFactory

        from apps.core.admin_site import sidebar_navigation

        request = RequestFactory().get("/admin/")
        request.user = user
        return {item["title"]: item for group in sidebar_navigation(request) for item in group["items"]}

    def test_badges_only_when_work_is_waiting(self):
        root = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        self.assertNotIn("badge", self.navigation(root)["Profiles"])
        make_profile(status=ProfileStatus.PENDING_REVIEW)
        self.assertEqual(self.navigation(root)["Profiles"]["badge"], "1")

    def test_sidebar_page_renders_for_superuser(self):
        root = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        make_profile(status=ProfileStatus.PENDING_REVIEW)
        self.client.force_login(root)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Members &amp; profiles")
        self.assertContains(response, "Admin activity log")
