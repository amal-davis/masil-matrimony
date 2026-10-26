from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.profiles.photos import PhotoRejected, process_upload

from .models import StoryStatus, SuccessStory
from .views import story_image_url


class SuccessStoryForm(forms.ModelForm):
    class Meta:
        model = SuccessStory
        fields = "__all__"
        # Unfold's own widget, so the boxes match the admin's other inputs (a plain forms.Textarea is unstyled).
        widgets = {
            "summary": UnfoldAdminTextareaWidget(attrs={"rows": 3}),
            "body": UnfoldAdminTextareaWidget(attrs={"rows": 18}),
        }

    def clean_slug(self):
        """Filled in from the title as staff type it; a taken address gets "-2", "-3"… instead of an error."""
        slug = slugify(self.cleaned_data.get("slug") or "")
        if slug and "slug" in self.changed_data:
            slug = self.instance._unique_slug(slug)
        return slug

    def clean_image(self):
        """A new upload is checked by its content and re-encoded (apps.profiles.photos), like member photos."""
        upload = self.cleaned_data.get("image")
        if isinstance(upload, UploadedFile):
            try:
                content, width, height = process_upload(upload)
            except PhotoRejected as error:
                raise ValidationError(str(error)) from None
            self._image_size = (width, height)
            return content
        return upload

    def save(self, commit=True):
        story = super().save(commit=False)
        if hasattr(self, "_image_size"):
            story.image_width, story.image_height = self._image_size
        if commit:
            story.save()
        return story


@admin.register(SuccessStory)
class SuccessStoryAdmin(ModelAdmin):
    form = SuccessStoryForm
    list_display = ["title", "thumbnail", "status", "couple_consent", "published_at", "display_order", "updated_at"]
    list_filter = ["status", "couple_consent"]
    search_fields = ["title", "couple_names", "summary"]
    search_help_text = "Search by title, couple's names or short description."
    ordering = ["display_order", "-published_at", "-pk"]
    sortable_by = ["title", "status", "published_at", "display_order", "updated_at"]
    readonly_fields = ["preview", "public_id", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["title", "slug", "couple_names", "summary", "body"]}),
        ("Image", {"fields": ["image", "preview", "image_alt"]}),
        ("Publishing", {"fields": ["couple_consent", "status", "published_at", "display_order"]}),
        ("Record", {"fields": ["public_id", "created_at", "updated_at"]}),
    ]
    actions = ["publish", "unpublish"]

    def get_prepopulated_fields(self, request, obj=None):
        # Fills the slug from the title while typing. Not once it's locked (read-only) after publishing.
        return {} if obj is not None and obj.published_at else {"slug": ("title",)}

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        # Fixed once published, so links people have shared keep working.
        return [*fields, "slug"] if obj is not None and obj.published_at else fields

    @admin.display(description="Image")
    def thumbnail(self, story):
        if not story.image:
            return "—"
        return format_html('<img src="{}" alt="" style="height:48px;border-radius:4px">', story_image_url(story))

    @admin.display(description="Current image")
    def preview(self, story):
        if not story or not story.image:
            return "No image yet."
        return format_html('<img src="{}" alt="" style="max-height:220px;border-radius:6px">', story_image_url(story))

    def save_model(self, request, obj, form, change):
        old_name = None
        if change and "image" in form.changed_data:
            old_name = SuccessStory.objects.filter(pk=obj.pk).values_list("image", flat=True).first()
        super().save_model(request, obj, form, change)
        if old_name and old_name != obj.image.name:
            storage = obj.image.storage
            # Removed only once the new image is safely saved.
            transaction.on_commit(lambda: storage.delete(old_name))

    @admin.action(description="Publish selected stories", permissions=["change"])
    def publish(self, request, queryset):
        published = 0
        for story in queryset.exclude(status=StoryStatus.PUBLISHED):
            story.status = StoryStatus.PUBLISHED
            try:
                story.full_clean()
            except ValidationError as error:
                problems = "; ".join(message for messages_ in error.message_dict.values() for message in messages_)
                self.message_user(request, f"“{story.title}” not published: {problems}", messages.WARNING)
                continue
            if story.published_at and story.published_at > timezone.now():
                self.message_user(request, f"“{story.title}” is scheduled for {story.published_at:%d %b %Y %H:%M}.")
            story.save()
            self.log_change(request, story, "Published.")
            published += 1
        self.message_user(request, f"Published {published} story(ies).")

    @admin.action(description="Unpublish selected stories (back to draft)", permissions=["change"])
    def unpublish(self, request, queryset):
        count = 0
        for story in queryset.filter(status=StoryStatus.PUBLISHED):
            story.status = StoryStatus.DRAFT
            story.save(update_fields=["status", "updated_at"])
            self.log_change(request, story, "Unpublished.")
            count += 1
        self.message_user(request, f"Unpublished {count} story(ies). They're no longer on the website.")
