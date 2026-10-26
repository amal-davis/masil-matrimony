"""
Content managed by content managers for the public website. Today: success
stories (pages, banners, FAQs and SEO metadata are planned; see
docs/database-design.md).
"""
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class StoryStatus(models.TextChoices):
    DRAFT = "draft", "Draft (not on the website)"
    PUBLISHED = "published", "Published"


def story_image_path(instance, filename):
    # Random names only: nothing from the uploaded file name reaches the disk.
    return f"success-stories/{uuid.uuid4().hex}.jpg"


class SuccessStoryQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=StoryStatus.PUBLISHED, published_at__lte=timezone.now())


class SuccessStory(TimeStampedModel):
    """
    A couple's story, written or approved by staff, shown on /success-stories.

    The image is re-encoded on upload (apps.website_content.admin) and served
    only while the story is published (apps.website_content.views.StoryImageView).
    The URL slug is fixed once the story is first published, so changing the
    title later doesn't break links people have shared.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=120)
    slug = models.SlugField(
        max_length=140, unique=True, blank=True,
        help_text="The story's web address (/success-stories/<slug>). Filled in automatically as you type the title; "
        "you can still edit it. Fixed once the story is published so shared links keep working.",
    )
    couple_names = models.CharField(
        max_length=80, blank=True, help_text='Optional, exactly as the couple agreed to be named, e.g. "Anu & Rahul".'
    )
    summary = models.CharField(
        "Short description", max_length=280, help_text="One or two sentences for the story card (up to 280 characters)."
    )
    body = models.TextField(
        "Full story", max_length=20000,
        help_text="Plain text. Leave an empty line between paragraphs. No HTML.",
    )
    image = models.FileField("Main image", upload_to=story_image_path, max_length=200, blank=True)
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_alt = models.CharField(
        "Image description", max_length=160, blank=True,
        help_text="Describes the photo for people using screen readers, e.g. \"Anu and Rahul at their wedding\".",
    )
    couple_consent = models.BooleanField(
        "Couple's consent", default=False,
        help_text="The couple agreed to publish this story, their names (if given) and photo on the public website.",
    )
    status = models.CharField(max_length=10, choices=StoryStatus.choices, default=StoryStatus.DRAFT, db_index=True)
    published_at = models.DateTimeField(
        "Publication date", null=True, blank=True,
        help_text="Set when first published. A future date keeps the story hidden until then.",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Lower numbers appear first; ties show the newest publication first."
    )

    objects = SuccessStoryQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "-published_at", "-pk"]
        verbose_name = "success story"
        verbose_name_plural = "success stories"
        indexes = [models.Index(fields=["status", "published_at"])]

    def __str__(self):
        return self.title

    @property
    def is_public(self) -> bool:
        return self.status == StoryStatus.PUBLISHED and self.published_at is not None and self.published_at <= timezone.now()

    def _unique_slug(self, base: str) -> str:
        base = (slugify(base) or "story")[:120]
        candidate, n = base, 2
        while SuccessStory.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    def clean(self):
        errors = {}
        if self.slug:
            self.slug = slugify(self.slug)
        if self.pk:
            previous = SuccessStory.objects.filter(pk=self.pk).values("slug", "published_at").first()
            if previous and previous["published_at"] and self.slug != previous["slug"]:
                errors["slug"] = "This story has been published, so its web address can't change (shared links would break)."
        if self.status == StoryStatus.PUBLISHED:
            if not self.couple_consent:
                errors["couple_consent"] = "Confirm the couple's consent before publishing."
            if not self.image:
                errors["image"] = "Add the main image before publishing."
            if not self.image_alt.strip():
                errors["image_alt"] = "Describe the image before publishing."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(self.title)
        if self.status == StoryStatus.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
