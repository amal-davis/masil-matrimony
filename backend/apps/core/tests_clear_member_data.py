"""clear_member_data: removes members and their data, keeps staff and site content, restarts id counters."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TransactionTestCase, override_settings

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.enquiries.models import Enquiry
from apps.interactions.models import Interest
from apps.memberships import assistance
from apps.memberships.models import AssistanceRequest, MembershipPackage, Subscription
from apps.memberships.tests import subscribe
from apps.memberships.tests_gold import make_staff
from apps.notifications.models import Notification
from apps.profiles.models import Profile
from apps.profiles.test_utils import make_profile, make_user
from apps.website_content.models import SuccessStory


@override_settings(DEBUG=True)
class ClearMemberDataTests(TransactionTestCase):
    # Restores the seeded packages and stories for later tests (they're data migrations).
    serialized_rollback = True

    def setUp(self):
        self.superuser = make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.matchmaker = make_staff("assign")
        self.groom, self.bride = make_profile(gender="male"), make_profile(gender="female")
        Interest.objects.create(sender=self.groom, receiver=self.bride)
        case = assistance.open_service_case(subscribe(self.groom.user, "platinum"))
        assistance.staff_update(case, self.matchmaker, status="assigned", assigned_to=self.matchmaker)
        assistance.start_exchange(case, self.bride, self.matchmaker, "Families agreed to talk.")
        self.stories = SuccessStory.objects.count()
        self.packages = MembershipPackage.objects.count()
        Enquiry.objects.create(name="Visitor", email="v@example.com", phone="+919800000001", message="Hello")

    def run_command(self, *args):
        out = StringIO()
        call_command("clear_member_data", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self.run_command()
        self.assertIn("Would delete 2 member account(s)", output)
        self.assertEqual((User.objects.filter(role=Role.MEMBER).count(), Profile.objects.count()), (2, 2))

    def test_deletes_members_and_their_data_and_keeps_everything_else(self):
        enquiries = Enquiry.objects.count()
        output = self.run_command("--confirm")
        self.assertIn("Deleted 2 member account(s)", output)
        self.assertFalse(User.objects.filter(role=Role.MEMBER).exists())
        for model in (Profile, Interest, Subscription, AssistanceRequest, Notification):
            self.assertFalse(model.objects.exists(), model.__name__)
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.matchmaker.pk).exists())
        self.assertEqual((SuccessStory.objects.count(), MembershipPackage.objects.count(), Enquiry.objects.count()),
                         (self.stories, self.packages, enquiries))
        self.assertEqual(enquiries, 1)

    def test_emptied_tables_start_again_at_one(self):
        self.run_command("--confirm")
        profile = make_profile(gender="male")
        self.assertEqual(profile.pk, 1)
        top_staff = User.objects.order_by("-pk").values_list("pk", flat=True)[1]
        self.assertEqual(profile.user_id, top_staff + 1)  # accounts continue after the staff that stayed

    @override_settings(DEBUG=False)
    def test_refuses_in_production(self):
        with self.assertRaises(CommandError):
            self.run_command("--confirm")
        self.assertEqual(Profile.objects.count(), 2)

