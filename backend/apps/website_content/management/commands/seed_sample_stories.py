"""
DEVELOPMENT ONLY: save fictional sample success stories in the database, so the
homepage slider and /success-stories have content while building the site.

    python manage.py seed_sample_stories            # add or refresh the samples
    python manage.py seed_sample_stories --remove   # delete them (and their images)

The stories are the same fictional samples as the frontend's design preview
(frontend/features/success-stories/demo-stories.ts), with the same stock photos
(frontend/public/images/hero, Unsplash). No real couple wrote them and the
people pictured are not Maasil members, so the command refuses to run unless
DEBUG is on, and every sample says it is a sample. Run it again at any time: it
updates the samples in place (by slug, all starting "sample-") and never
touches other stories.
"""
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.profiles.photos import PhotoRejected, process_upload
from apps.website_content.models import StoryStatus, SuccessStory

SLUG_PREFIX = "sample-"
IMAGES_DIR = settings.BASE_DIR.parent / "frontend" / "public" / "images" / "hero"
NOTICE = "This is a sample story for local development. It is fictional, and the people in the photo are not Maasil members."

PHOTOS = {
    "lotus-field": ("couple-lotus-field.jpg", "A smiling couple in traditional dress among lotus flowers"),
    "garlanded": ("garlanded-couple.jpg", "A newly married couple wearing wedding garlands, smiling at each other"),
    "wedding-family": (
        "kerala-wedding-family.jpg",
        "A bride and groom in Kerala wedding attire surrounded by their families",
    ),
}

SAMPLES = [
    {
        "title": "A Beautiful Beginning",
        "photo": "lotus-field",
        "summary": "We found someone who shared our values and dreams. The experience helped both our families take "
        "the next step with confidence.",
        "body": [
            "We had both been searching for a while, and we wanted someone who understood what family means to us.",
            "Our first conversation went on for hours. By the second visit, our parents were already planning the "
            "next one.",
        ],
    },
    {
        "title": "Two Families, One Celebration",
        "photo": "garlanded",
        "summary": "Our parents spoke first, and we were grateful for that. By the time we met, it already felt as "
        "though our families knew each other well.",
        "body": [
            "Our families met before we did, over tea and a long talk about our home towns.",
            "When we finally met, there was no awkwardness at all. The wedding brought both families together in one "
            "big celebration.",
        ],
    },
    {
        "title": "Worth the Wait",
        "photo": "wedding-family",
        "summary": "We took our time and never felt rushed. Being able to share details at our own pace made every "
        "conversation feel honest.",
        "body": [
            "Neither of us wanted to hurry. We spoke for months before deciding, and that patience made all the "
            "difference.",
            "Looking back, every step felt right because we took it together.",
        ],
    },
    {
        "title": "Across the Miles",
        "photo": "garlanded",
        "summary": "We were working in different cities, yet the search kept our preferences close to home. Distance "
        "never felt like a barrier.",
        "body": [
            "One of us was in Bengaluru and the other in Dubai, but both our families are from Thrissur.",
            "Video calls turned into visits home, and visits home turned into a wedding date.",
        ],
    },
    {
        "title": "Guided With Care",
        "photo": "wedding-family",
        "summary": "Our advisor listened to what mattered to our family and helped us shortlist thoughtfully. We always "
        "knew who to call with a question.",
        "body": [
            "Our parents were new to online matrimony, and the support team patiently answered every question.",
            "With their help we found a match who felt like family from the very first meeting.",
        ],
    },
    {
        "title": "A Promise for Tomorrow",
        "photo": "lotus-field",
        "summary": "From the first visit to the wedding day, everything felt natural. We are starting our life together "
        "with the blessings of both families.",
        "body": [
            "It started with a simple interest request and a phone call between our mothers.",
            "Today we are building our home together, grateful for the families who brought us here.",
        ],
    },
]


def _slug(title: str) -> str:
    return SLUG_PREFIX + "-".join("".join(c if c.isalnum() else " " for c in title.lower()).split())


class Command(BaseCommand):
    help = "DEVELOPMENT ONLY: add (or with --remove, delete) fictional sample success stories."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete the sample stories and their images.")

    def handle(self, *args, remove=False, **options):
        if not settings.DEBUG:
            raise CommandError("Sample stories are fictional: this command only runs with DEBUG on (development).")
        if remove:
            self._remove()
        else:
            self._seed()

    def _remove(self):
        stories = list(SuccessStory.objects.filter(slug__startswith=SLUG_PREFIX))
        for story in stories:
            if story.image:
                story.image.delete(save=False)
            story.delete()
        self.stdout.write(self.style.SUCCESS(f"Removed {len(stories)} sample stories."))

    def _seed(self):
        images = {}
        for key, (filename, _alt) in PHOTOS.items():
            path = Path(IMAGES_DIR) / filename
            if not path.is_file():
                raise CommandError(f"Sample photo not found: {path}")
            with path.open("rb") as handle:
                try:
                    images[key] = process_upload(File(handle, name=filename))
                except PhotoRejected as error:
                    raise CommandError(f"{filename}: {error}") from None

        created = 0
        now = timezone.now()
        with transaction.atomic():
            for order, sample in enumerate(SAMPLES, start=1):
                slug = _slug(sample["title"])
                story = SuccessStory.objects.filter(slug=slug).first() or SuccessStory(slug=slug)
                created += story.pk is None
                content, width, height = images[sample["photo"]]
                if story.image:
                    story.image.delete(save=False)  # replaced below, so re-running leaves no stray files
                story.image.save("photo.jpg", content, save=False)
                story.image_width, story.image_height = width, height
                story.title = sample["title"]
                story.summary = sample["summary"]
                story.body = "\n\n".join([*sample["body"], NOTICE])
                story.image_alt = PHOTOS[sample["photo"]][1]
                story.couple_names = ""
                story.couple_consent = True  # needed to publish; the samples are fictional (see NOTICE)
                story.status = StoryStatus.PUBLISHED
                story.published_at = story.published_at or now
                # After the real stories (which default to 0), in the order above.
                story.display_order = 100 + order
                story.full_clean()
                story.save()

        updated = len(SAMPLES) - created
        self.stdout.write(self.style.SUCCESS(f"Sample stories saved: {created} added, {updated} updated."))
