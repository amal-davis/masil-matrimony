"""Success stories: admin workflow, image handling, the public API and access rules."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.profiles.test_utils import TempMediaMixin, client_for, image_bytes, make_user, upload

from .models import StoryStatus, SuccessStory
from .views import paragraphs

LIST = "/api/v1/success-stories/"


def form_data(**overrides):
    return {
        "title": "A Beautiful Beginning", "slug": "", "couple_names": "Anu & Rahul",
        "summary": "Two families from Thrissur found each other.",
        "body": "We met through Massil.\n\nOur families talked for months.\nThen we married.",
        "image_alt": "Anu and Rahul at their wedding", "couple_consent": "on", "status": StoryStatus.PUBLISHED,
        "published_at_0": "", "published_at_1": "", "display_order": "0", **overrides,
    }


class StoryTestCase(TempMediaMixin, TestCase):
    def setUp(self):
        self.root = make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.add_url = reverse("admin:website_content_successstory_add")

    def add_story(self, client=None, image=True, **overrides):
        data = form_data(**overrides)
        if image:
            data["image"] = upload()
        client = client or self.client
        client.force_login(self.root) if client is self.client else None
        return client.post(self.add_url, data)

    def published(self, **fields):
        fields.setdefault("title", "A Story")
        fields.setdefault("summary", "Short.")
        fields.setdefault("body", "Long story.")
        fields.setdefault("couple_consent", True)
        fields.setdefault("image_alt", "Couple")
        fields.setdefault("status", StoryStatus.PUBLISHED)
        story = SuccessStory(**fields)
        story.image.save("x.jpg", upload(image_bytes()), save=False)
        story.save()
        return story


class AdminWorkflowTests(StoryTestCase):
    def test_create_with_image_upload_and_publish(self):
        response = self.add_story()
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        story = SuccessStory.objects.get()
        self.assertEqual((story.slug, story.status), ("a-beautiful-beginning", StoryStatus.PUBLISHED))
        self.assertIsNotNone(story.published_at)
        self.assertTrue(story.image.name.startswith("success-stories/") and story.image.name.endswith(".jpg"))
        self.assertTrue(story.image.storage.exists(story.image.name))
        self.assertEqual((story.image_width, story.image_height), (400, 500))

    def test_invalid_and_oversized_uploads_are_rejected(self):
        self.client.force_login(self.root)
        fake = upload(b"<?php echo 'not an image'; ?>", name="photo.jpg", content_type="image/jpeg")
        response = self.client.post(self.add_url, {**form_data(), "image": fake})
        self.assertContains(response, "isn&#x27;t a photo we can read")
        with override_settings(PROFILE_PHOTO_MAX_BYTES=10):
            response = self.client.post(self.add_url, {**form_data(), "image": upload()})
        self.assertContains(response, "larger than")
        self.assertFalse(SuccessStory.objects.exists())

    def test_publishing_needs_consent_image_and_description(self):
        self.client.force_login(self.root)
        response = self.client.post(self.add_url, {**form_data(couple_consent="", image_alt=""), "image": upload()})
        self.assertContains(response, "Confirm the couple&#x27;s consent")
        self.assertContains(response, "Describe the image")
        response = self.client.post(self.add_url, form_data())  # no image
        self.assertContains(response, "Add the main image")
        # A draft can be saved without them.
        self.assertEqual(self.client.post(self.add_url, form_data(status="draft", couple_consent="")).status_code, 302)

    def test_publish_and_unpublish_actions(self):
        story = self.published(status=StoryStatus.DRAFT)
        self.client.force_login(self.root)
        changelist = reverse("admin:website_content_successstory_changelist")
        self.client.post(changelist, {"action": "publish", "_selected_action": [story.pk]})
        story.refresh_from_db()
        self.assertTrue(story.is_public)
        self.client.post(changelist, {"action": "unpublish", "_selected_action": [story.pk]})
        story.refresh_from_db()
        self.assertEqual(story.status, StoryStatus.DRAFT)
        self.assertEqual(client_for().get(f"{LIST}{story.slug}/").status_code, 404)

    def test_publish_action_refuses_stories_without_consent(self):
        story = self.published(status=StoryStatus.DRAFT, couple_consent=False)
        self.client.force_login(self.root)
        response = self.client.post(reverse("admin:website_content_successstory_changelist"),
                                    {"action": "publish", "_selected_action": [story.pk]}, follow=True)
        self.assertContains(response, "not published")
        story.refresh_from_db()
        self.assertEqual(story.status, StoryStatus.DRAFT)

    def test_replacing_the_image_removes_the_old_file(self):
        self.add_story()
        story = SuccessStory.objects.get()
        old = story.image.name
        change = reverse("admin:website_content_successstory_change", args=[story.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(change, {**form_data(), "image": upload(image_bytes(color=(10, 200, 10)))})
        story.refresh_from_db()
        self.assertNotEqual(story.image.name, old)
        self.assertFalse(story.image.storage.exists(old))
        self.assertTrue(story.image.storage.exists(story.image.name))

    def test_staff_need_permissions(self):
        staff = make_user(role=Role.CONTENT_MANAGER, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        for codename in ("view_successstory", "add_successstory"):
            staff.user_permissions.add(Permission.objects.get(codename=codename))
        self.assertEqual(self.client.get(self.add_url).status_code, 200)
        # Members can't write stories through the API: it's read-only.
        member = client_for(make_user())
        self.assertEqual(member.post(LIST, {"title": "x"}, format="json").status_code, 405)


class SlugTests(StoryTestCase):
    def test_slugs_are_unique_and_fixed_once_published(self):
        first = self.published(title="Our Story")
        second = self.published(title="Our Story")
        self.assertEqual((first.slug, second.slug), ("our-story", "our-story-2"))
        first.title = "A Completely New Title"
        first.full_clean()
        first.save()
        first.refresh_from_db()
        self.assertEqual(first.slug, "our-story")
        first.slug = "something-else"
        with self.assertRaises(ValidationError):
            first.full_clean()

    def test_add_page_fills_the_slug_from_the_title(self):
        self.client.force_login(self.root)
        page = self.client.get(self.add_url)
        self.assertContains(page, "data-prepopulated-fields")
        self.assertContains(page, "#id_slug")
        self.assertContains(page, "#id_title")

    def test_text_boxes_use_the_admin_input_style(self):
        import re

        self.client.force_login(self.root)
        html = self.client.get(self.add_url).content.decode()
        for name in ("title", "slug", "summary", "body", "image_alt"):
            with self.subTest(field=name):
                tag = re.search(rf'<(?:input|textarea)[^>]*name="{name}"[^>]*>', html).group(0)
                self.assertIn("border-base-200", tag)
                self.assertIn("rounded-default", tag)

    def test_a_taken_slug_gets_a_suffix_instead_of_an_error(self):
        self.published(title="A Beautiful Beginning")
        response = self.add_story(slug="a-beautiful-beginning")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SuccessStory.objects.latest("pk").slug, "a-beautiful-beginning-2")

    def test_slug_is_read_only_in_the_admin_after_publishing(self):
        story = self.published()
        self.client.force_login(self.root)
        page = self.client.get(reverse("admin:website_content_successstory_change", args=[story.pk]))
        self.assertNotContains(page, 'name="slug"')


class PublicApiTests(StoryTestCase):
    def test_list_returns_only_published_stories_with_card_fields(self):
        story = self.published(title="Visible", summary="Short words.", body="The whole long story.")
        self.published(title="Draft", status=StoryStatus.DRAFT)
        self.published(title="Scheduled", published_at=timezone.now() + timedelta(days=3))
        body = client_for().get(LIST).json()
        self.assertEqual([item["title"] for item in body["results"]], ["Visible"])
        card = body["results"][0]
        self.assertEqual(set(card), {"id", "slug", "title", "couple_names", "summary", "image", "published_at"})
        self.assertEqual(card["summary"], "Short words.")
        self.assertNotIn("The whole long story", str(card))
        self.assertEqual(card["image"]["alt"], "Couple")
        self.assertTrue(card["image"]["url"].startswith("http://testserver/api/v1/success-stories/images/"))
        self.assertNotIn("success-stories/", card["image"]["url"].split("/images/")[1])  # no file path
        self.assertNotIn("media", card["image"]["url"])
        self.assertEqual(body["count"], 1)
        self.assertNotIn("couple_consent", str(body))
        self.assertEqual(card["slug"], story.slug)

    def test_detail_returns_the_full_story_as_paragraphs(self):
        story = self.published(body="First paragraph.\n\nSecond line one\nline two.\r\n\r\n\r\nThird.")
        body = client_for().get(f"{LIST}{story.slug}/").json()
        self.assertEqual(body["paragraphs"], ["First paragraph.", "Second line one line two.", "Third."])
        self.assertEqual(body["title"], story.title)

    def test_drafts_missing_and_scheduled_stories_are_not_found(self):
        draft = self.published(status=StoryStatus.DRAFT)
        later = self.published(published_at=timezone.now() + timedelta(days=1))
        for slug in (draft.slug, later.slug, "no-such-story"):
            with self.subTest(slug=slug):
                response = client_for().get(f"{LIST}{slug}/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Story not found."})

    def test_html_is_never_interpreted(self):
        story = self.published(body="<script>alert(1)</script>\n\nHello")
        self.assertEqual(client_for().get(f"{LIST}{story.slug}/").json()["paragraphs"][0], "<script>alert(1)</script>")

    def test_ordering_is_deterministic_and_paginated(self):
        old = self.published(title="Old", published_at=timezone.now() - timedelta(days=9))
        new = self.published(title="New")
        pinned = self.published(title="Pinned", display_order=0)
        SuccessStory.objects.filter(pk__in=[old.pk, new.pk]).update(display_order=5)
        titles = [item["title"] for item in client_for().get(LIST).json()["results"]]
        self.assertEqual(titles, ["Pinned", "New", "Old"])
        for i in range(20):
            self.published(title=f"Extra {i}")
        first, second = client_for().get(LIST).json(), client_for().get(LIST, {"page": 2}).json()
        self.assertEqual((len(first["results"]), len(second["results"]), first["count"]), (20, 3, 23))
        self.assertFalse({i["slug"] for i in first["results"]} & {i["slug"] for i in second["results"]})

    def test_query_count_is_constant(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.published()

        def count():
            with CaptureQueriesContext(connection) as queries:
                client_for().get(LIST)
            return len(queries)

        few = count()
        for _ in range(4):
            self.published()
        self.assertEqual(count(), few)

    @override_settings(API_PUBLIC_URL="https://api.example.com/")
    def test_public_api_url_is_used_without_double_slashes(self):
        self.published()
        url = client_for().get(LIST).json()["results"][0]["image"]["url"]
        self.assertTrue(url.startswith("https://api.example.com/api/v1/success-stories/images/"))


class ImageViewTests(StoryTestCase):
    def test_published_image_is_served_and_draft_image_is_not(self):
        story = self.published()
        url = client_for().get(LIST).json()["results"][0]["image"]["url"]
        response = self.client.get(url)
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "image/jpeg"))
        self.assertIn("public", response["Cache-Control"])
        story.status = StoryStatus.DRAFT
        story.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        # Staff can still preview it in the admin.
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_paragraph_helper(self):
        self.assertEqual(paragraphs(""), [])
        self.assertEqual(paragraphs("  one  \n\n\n two "), ["one", "two"])


@override_settings(DEBUG=True)
class SampleStoriesCommandTests(TempMediaMixin, TestCase):
    """manage.py seed_sample_stories: fictional stories for local development only."""

    def run_command(self, *args):
        call_command("seed_sample_stories", *args, stdout=StringIO())

    def test_adds_six_published_samples_with_images_and_is_safe_to_rerun(self):
        real = SuccessStory.objects.create(title="Our story", summary="Real.", body="Real story.")
        self.run_command()
        self.run_command()

        samples = SuccessStory.objects.filter(slug__startswith="sample-")
        self.assertEqual(samples.count(), 6)
        self.assertEqual(SuccessStory.objects.published().filter(slug__startswith="sample-").count(), 6)
        for story in samples:
            self.assertTrue(story.image and story.image_width and story.image_alt)
            self.assertIn("sample story for local development", story.body)
        response = self.client.get(LIST)
        self.assertEqual(response.json()["count"], 6)  # the real story is still a draft
        self.assertTrue(SuccessStory.objects.filter(pk=real.pk).exists())

    def test_remove_deletes_only_the_samples(self):
        real = SuccessStory.objects.create(title="Our story", summary="Real.", body="Real story.")
        self.run_command()
        storage = SuccessStory._meta.get_field("image").storage
        names = [story.image.name for story in SuccessStory.objects.filter(slug__startswith="sample-")]

        self.run_command("--remove")
        self.assertEqual(list(SuccessStory.objects.all()), [real])
        self.assertFalse(any(storage.exists(name) for name in names))

    @override_settings(DEBUG=False)
    def test_refuses_to_run_without_debug(self):
        with self.assertRaises(CommandError):
            self.run_command()
        self.assertFalse(SuccessStory.objects.exists())
