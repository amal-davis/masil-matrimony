from django.contrib import admin, messages
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from .choices import PhotoStatus, ProfileStatus
from .models import PartnerPreference, Profile, ProfilePhoto
from .photos import signed_photo_url


class PartnerPreferenceInline(StackedInline):
    model = PartnerPreference
    can_delete = False
    extra = 0


class ProfilePhotoInline(TabularInline):
    model = ProfilePhoto
    extra = 0
    fields = ["preview", "status", "review_note", "is_primary", "created_at"]
    # Status changes only through the photo actions, which notify the member.
    readonly_fields = ["preview", "status", "is_primary", "created_at"]
    can_delete = False

    @admin.display(description="Photo")
    def preview(self, photo):
        return format_html('<img src="{}" alt="" style="height:96px;border-radius:4px">', signed_photo_url(photo))


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    list_display = ["profile_code", "display_name", "gender", "status", "account", "submitted_at", "reviewed_at"]
    list_filter = ["status", "gender", "religion", "visibility", "created_for"]
    list_select_related = ["user"]
    search_fields = ["profile_code", "display_name", "user__email", "user__phone_number"]
    search_help_text = "Search by Matrimony ID, name, email or mobile number."
    ordering = ["-created_at"]
    list_per_page = 50
    # Status changes only through "Approve" and "Request changes", which record the
    # reviewer and notify the member; it can't be edited directly.
    readonly_fields = [
        "public_id", "profile_code", "account", "status", "submitted_at", "reviewed_at", "reviewed_by",
        "created_at", "updated_at",
    ]
    inlines = [PartnerPreferenceInline, ProfilePhotoInline]
    actions = ["approve", "request_changes"]

    @admin.display(description="Account", ordering="user__email")
    def account(self, profile):
        url = reverse("admin:accounts_user_change", args=[profile.user_id])
        return format_html('<a href="{}">{}</a>', url, profile.user.email)

    @admin.action(description="Approve selected profiles (make them visible to members)", permissions=["change"])
    def approve(self, request, queryset):
        count = 0
        with transaction.atomic():
            for profile in queryset.select_for_update().filter(status=ProfileStatus.PENDING_REVIEW):
                profile.status = ProfileStatus.ACTIVE
                profile.review_note = ""
                profile.reviewed_at = timezone.now()
                profile.reviewed_by = request.user
                profile.save()
                notify(
                    profile.user,
                    NotificationKind.PROFILE_APPROVED,
                    "Your profile has been approved",
                    "Your profile is now visible to other members.",
                    "/dashboard",
                )
                self.log_change(request, profile, "Approved.")
                count += 1
        self.message_user(request, f"Approved {count} profile(s). Only profiles pending review are changed.")

    @admin.action(description="Request changes (write the reason in 'Review note' first)", permissions=["change"])
    def request_changes(self, request, queryset):
        count = 0
        with transaction.atomic():
            for profile in queryset.select_for_update().filter(status=ProfileStatus.PENDING_REVIEW):
                if not profile.review_note:
                    self.message_user(
                        request, f"{profile.profile_code}: add a review note before requesting changes.", messages.WARNING
                    )
                    continue
                profile.status = ProfileStatus.REJECTED
                profile.reviewed_at = timezone.now()
                profile.reviewed_by = request.user
                profile.save()
                notify(
                    profile.user,
                    NotificationKind.PROFILE_CHANGES_REQUESTED,
                    "Your profile needs a few changes",
                    profile.review_note,
                    "/dashboard/my-profile",
                )
                self.log_change(request, profile, "Changes requested.")
                count += 1
        self.message_user(request, f"Returned {count} profile(s) to their members.")


@admin.register(ProfilePhoto)
class ProfilePhotoAdmin(ModelAdmin):
    list_display = ["preview", "profile", "status", "is_primary", "created_at"]
    list_filter = ["status"]
    list_select_related = ["profile"]
    search_fields = ["profile__profile_code"]
    search_help_text = "Search by Matrimony ID."
    ordering = ["-created_at"]
    list_per_page = 50
    # Status changes only through "Approve" and "Reject", which notify the member.
    readonly_fields = [
        "public_id", "profile", "preview", "status", "width", "height", "is_primary", "created_at", "reviewed_at",
    ]
    exclude = ["image"]
    actions = ["approve", "reject"]

    def has_add_permission(self, request):
        return False  # photos are uploaded by members through the API, which validates them

    @admin.display(description="Photo")
    def preview(self, photo):
        return format_html('<img src="{}" alt="" style="height:72px;border-radius:4px">', signed_photo_url(photo))

    def _review(self, request, queryset, status, kind, title, body):
        count = 0
        with transaction.atomic():
            for photo in queryset.select_for_update().select_related("profile__user").exclude(status=status):
                photo.status = status
                photo.reviewed_at = timezone.now()
                photo.save()
                notify(photo.profile.user, kind, title, photo.review_note or body, "/dashboard/photos")
                self.log_change(request, photo, f"Marked {photo.get_status_display().lower()}.")
                count += 1
        self.message_user(request, f"Updated {count} photo(s).")

    @admin.action(description="Approve selected photos", permissions=["change"])
    def approve(self, request, queryset):
        self._review(
            request, queryset, PhotoStatus.APPROVED, NotificationKind.PHOTO_APPROVED,
            "Your photo has been approved", "Members can now see this photo, subject to your privacy settings.",
        )

    @admin.action(description="Reject selected photos (add a review note to explain)", permissions=["change"])
    def reject(self, request, queryset):
        self._review(
            request, queryset, PhotoStatus.REJECTED, NotificationKind.PHOTO_REJECTED,
            "A photo wasn't approved", "Please upload a clear, recent photo of yourself.",
        )
