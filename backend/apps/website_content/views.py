"""
Public, read-only success stories:

    GET /api/v1/success-stories/                 published stories, paginated (cards)
    GET /api/v1/success-stories/<slug>/          one published story (full text)
    GET /api/v1/success-stories/images/<id>/     its image, only while published

Drafts, unpublished and scheduled stories are 404 to everyone except signed-in
staff in the admin, who can preview images. The full story is plain text, sent
as a list of paragraphs, never HTML.
"""
import re

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views import View
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from .models import SuccessStory


def story_image_url(story: SuccessStory, request=None) -> str:
    """Where the story's image is served. `v` changes with every edit, so a replaced image is never stale."""
    path = f"{reverse('website_content:story-image', args=[story.public_id])}?v={int(story.updated_at.timestamp())}"
    if settings.API_PUBLIC_URL:
        return f"{settings.API_PUBLIC_URL.rstrip('/')}{path}"
    return request.build_absolute_uri(path) if request else path


def image_data(story: SuccessStory, request) -> dict | None:
    if not story.image:
        return None
    return {
        "url": story_image_url(story, request),
        "width": story.image_width,
        "height": story.image_height,
        "alt": story.image_alt,
    }


def paragraphs(text: str) -> list[str]:
    """The story split on empty lines; single line breaks inside a paragraph become spaces."""
    blocks = re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip())
    return [" ".join(block.split()) for block in blocks if block.strip()]


def card_data(story: SuccessStory, request) -> dict:
    return {
        "id": str(story.public_id),
        "slug": story.slug,
        "title": story.title,
        "couple_names": story.couple_names,
        "summary": story.summary,
        "image": image_data(story, request),
        "published_at": story.published_at,
    }


class StoryListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["website"])
    def get(self, request):
        paginator = api_settings.DEFAULT_PAGINATION_CLASS()
        page = paginator.paginate_queryset(SuccessStory.objects.published(), request, view=self)
        return paginator.get_paginated_response([card_data(story, request) for story in page])


class StoryDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["website"])
    def get(self, request, slug):
        story = SuccessStory.objects.published().filter(slug=slug).first()
        if story is None:
            raise NotFound("Story not found.")
        return Response({**card_data(story, request), "paragraphs": paragraphs(story.body)})


class StoryImageView(View):
    """The image of a published story; staff signed in to the admin may also see drafts' images."""

    http_method_names = ["get", "head"]

    def get(self, request, public_id):
        story = SuccessStory.objects.filter(public_id=public_id).first()
        staff = request.user.is_authenticated and request.user.has_perm("website_content.view_successstory")
        if story is None or not story.image or not (story.is_public or staff):
            raise Http404
        response = FileResponse(story.image.open("rb"), content_type="image/jpeg")
        response["Cache-Control"] = "public, max-age=3600" if story.is_public else "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
