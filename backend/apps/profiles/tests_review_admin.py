"""The "Approve profile" / "Request changes" buttons on a profile's admin page."""
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import Role
from apps.notifications.models import Notification

from .choices import PhotoStatus, ProfileStatus
from .test_utils import TempMediaMixin, make_profile, make_user, upload


class ReviewButtonTests(TestCase):
    def setUp(self):
        self.profile = make_profile(status=ProfileStatus.PENDING_REVIEW)
        self.root = make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.client.force_login(self.root)
        self.change_url = reverse("admin:profiles_profile_change", args=[self.profile.pk])
        self.approve_url = reverse("admin:profiles_profile_approve_this", args=[self.profile.pk])
        self.changes_url = reverse("admin:profiles_profile_request_changes_this", args=[self.profile.pk])

    def test_buttons_are_on_the_profile_page(self):
        page = self.client.get(self.change_url)
        self.assertContains(page, self.approve_url)
        self.assertContains(page, self.changes_url)

    def test_opening_the_button_only_asks_for_confirmation(self):
        page = self.client.get(self.approve_url)
        self.assertContains(page, "Approve this profile?")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, ProfileStatus.PENDING_REVIEW)

    def test_confirming_approves_records_the_reviewer_and_notifies(self):
        response = self.client.post(self.approve_url)
        self.assertRedirects(response, self.change_url, fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.status, self.profile.reviewed_by), (ProfileStatus.ACTIVE, self.root))
        self.assertTrue(Notification.objects.filter(recipient=self.profile.user, kind="profile_approved").exists())

    def test_a_draft_cant_be_approved(self):
        self.profile.status = ProfileStatus.DRAFT
        self.profile.save()
        page = self.client.get(self.approve_url)
        self.assertContains(page, "can&#x27;t be approved yet")
        self.assertNotContains(page, "Yes, approve")
        self.client.post(self.approve_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, ProfileStatus.DRAFT)

    def test_request_changes_needs_a_saved_note(self):
        self.assertContains(self.client.get(self.changes_url), "Review note")
        self.client.post(self.changes_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, ProfileStatus.PENDING_REVIEW)
        self.profile.review_note = "Please add a clearer photo."
        self.profile.save()
        self.client.post(self.changes_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, ProfileStatus.REJECTED)

    def test_view_only_staff_cant_approve(self):
        viewer = make_user(role=Role.ADMIN, is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_profile"))
        self.client.force_login(viewer)
        self.client.post(self.approve_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, ProfileStatus.PENDING_REVIEW)


class PhotoReviewButtonTests(TempMediaMixin, TestCase):
    def setUp(self):
        from . import services

        self.profile = make_profile()
        self.first = services.add_photo(self.profile, upload())
        self.second = services.add_photo(self.profile, upload())
        self.client.force_login(make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True))
        self.profile_url = reverse("admin:profiles_profile_change", args=[self.profile.pk])
        self.approve_all_url = reverse("admin:profiles_profile_approve_photos_this", args=[self.profile.pk])

    def test_profile_page_has_an_approve_photos_button_that_confirms_first(self):
        self.assertContains(self.client.get(self.profile_url), self.approve_all_url)
        page = self.client.get(self.approve_all_url)
        self.assertContains(page, "Approve 2 photo(s) awaiting review?")
        self.assertContains(page, "/photo-files/")  # previews of the photos being approved
        self.assertEqual(set(self.profile.photos.values_list("status", flat=True)), {PhotoStatus.PENDING})

    def test_confirming_approves_all_pending_photos_and_notifies(self):
        self.client.post(self.approve_all_url)
        self.assertEqual(set(self.profile.photos.values_list("status", flat=True)), {PhotoStatus.APPROVED})
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user, kind="photo_approved").count(), 2)
        page = self.client.get(self.approve_all_url)
        self.assertContains(page, "No photos are waiting for review")

    def test_single_photo_buttons(self):
        photo_url = reverse("admin:profiles_profilephoto_change", args=[self.first.pk])
        approve = reverse("admin:profiles_profilephoto_approve_this", args=[self.first.pk])
        reject = reverse("admin:profiles_profilephoto_reject_this", args=[self.second.pk])
        page = self.client.get(photo_url)
        self.assertContains(page, approve)
        self.assertContains(self.client.get(approve), "Approve this photo?")
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, PhotoStatus.PENDING)  # GET changes nothing
        self.client.post(approve)
        self.client.post(reject)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual((self.first.status, self.second.status), (PhotoStatus.APPROVED, PhotoStatus.REJECTED))

    def test_view_only_staff_cant_approve_photos(self):
        viewer = make_user(role=Role.ADMIN, is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_profile"))
        viewer.user_permissions.add(Permission.objects.get(codename="view_profilephoto"))
        self.client.force_login(viewer)
        self.client.post(self.approve_all_url)
        self.client.post(reverse("admin:profiles_profilephoto_approve_this", args=[self.first.pk]))
        self.assertEqual(set(self.profile.photos.values_list("status", flat=True)), {PhotoStatus.PENDING})
