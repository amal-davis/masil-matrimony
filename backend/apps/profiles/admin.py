from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.decorators import action
from unfold.enums import ActionVariant

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from . import highlights
from .choices import PhotoStatus, ProfileStatus
from .models import PartnerPreference, Profile, ProfilePhoto
from .photos import signed_photo_url


PHOTO_APPROVED = (
    PhotoStatus.APPROVED, NotificationKind.PHOTO_APPROVED, "Your photo has been approved",
    "Members can now see this photo, subject to your privacy settings.",
)
PHOTO_REJECTED = (
    PhotoStatus.REJECTED, NotificationKind.PHOTO_REJECTED, "A photo wasn't approved",
    "Please upload a clear, recent photo of yourself.",
)


def review_photos(model_admin, request, queryset, status, kind, title, body) -> int:
    """Set the photos' review status, notify each member and log it. Returns how many changed."""
    count = 0
    with transaction.atomic():
        for photo in queryset.select_for_update().select_related("profile__user").exclude(status=status):
            photo.status = status
            photo.reviewed_at = timezone.now()
            photo.save()
            notify(photo.profile.user, kind, title, photo.review_note or body, "/dashboard/photos")
            model_admin.log_change(request, photo, f"Marked {photo.get_status_display().lower()}.")
            count += 1
    return count


def confirmation_page(model_admin, request, *, question, summary, detail, back_url, button_label, button_variant,
                      can_proceed, images=()):
    """The confirmation step a review button shows (GET). Its form posts back to the same button URL."""
    context = {
        **model_admin.admin_site.each_context(request),
        "title": question, "question": question, "summary": summary, "detail": detail, "images": list(images),
        "back_url": back_url, "button_label": button_label, "button_variant": button_variant,
        "can_proceed": can_proceed, "opts": model_admin.model._meta,
    }
    return TemplateResponse(request, "admin/profiles/profile/review_confirmation.html", context)


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
    list_display = [
        "profile_code", "display_name", "gender", "status", "account", "is_highlighted", "homepage", "submitted_at",
        "reviewed_at",
    ]
    list_filter = ["status", "is_highlighted", "homepage_consent", "gender", "religion", "visibility", "created_for"]
    list_select_related = ["user"]
    search_fields = ["profile_code", "display_name", "user__email", "user__phone_number"]
    search_help_text = "Search by Matrimony ID, name, email or mobile number."
    ordering = ["-created_at"]
    list_per_page = 50
    # Status changes only through "Approve" and "Request changes", which record the
    # reviewer and notify the member; it can't be edited directly. Contact sharing and
    # homepage consent are the member's own consent, so only the member can change them.
    readonly_fields = [
        "public_id", "profile_code", "account", "status", "contact_sharing", "homepage_consent", "homepage",
        "submitted_at", "reviewed_at", "reviewed_by", "created_at", "updated_at",
    ]
    inlines = [PartnerPreferenceInline, ProfilePhotoInline]
    actions = ["approve", "request_changes", "highlight", "remove_highlight"]
    # The same review steps as buttons at the top of a profile's own page.
    actions_detail = ["approve_this", "request_changes_this", "approve_photos_this"]

    HIGHLIGHT_FIELDS = ["is_highlighted", "highlight_order"]

    def has_highlight_permission(self, request, obj=None):
        return request.user.has_perm("profiles.highlight_profile")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        # Choosing homepage profiles needs its own permission, not just "change profile".
        return fields if self.has_highlight_permission(request) else fields + self.HIGHLIGHT_FIELDS

    @admin.display(description="Shown on homepage")
    def homepage(self, profile):
        if not profile.is_highlighted:
            return "—"
        reasons = highlights.why_hidden(profile)
        return "Yes" if not reasons else f"No: {'; '.join(reasons)}"

    def _warn_if_hidden(self, request, profile):
        reasons = highlights.why_hidden(profile)
        if reasons:
            self.message_user(
                request,
                f"{profile.profile_code} is highlighted but won't appear on the homepage until: {'; '.join(reasons)}.",
                messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if {"is_highlighted", "highlight_order"} & set(form.changed_data):
            self.log_change(request, obj, "Homepage highlight changed.")
        self._warn_if_hidden(request, obj)

    @admin.action(description="Highlight selected profiles on the homepage", permissions=["highlight"])
    def highlight(self, request, queryset):
        updated = 0
        for profile in queryset.select_related("user").filter(is_highlighted=False):
            profile.is_highlighted = True
            profile.save(update_fields=["is_highlighted", "updated_at"])
            self.log_change(request, profile, "Highlighted on homepage.")
            self._warn_if_hidden(request, profile)
            updated += 1
        self.message_user(request, f"Highlighted {updated} profile(s).")

    @admin.action(description="Remove selected profiles from the homepage", permissions=["highlight"])
    def remove_highlight(self, request, queryset):
        updated = 0
        for profile in queryset.filter(is_highlighted=True):
            profile.is_highlighted = False
            profile.save(update_fields=["is_highlighted", "updated_at"])
            self.log_change(request, profile, "Removed from homepage.")
            updated += 1
        self.message_user(request, f"Removed {updated} profile(s) from the homepage.")

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
        if count:
            self.message_user(request, f"Approved {count} profile(s). They're now visible to members.")
        else:
            self.message_user(
                request,
                "Nothing was approved: only profiles with status \"Pending review\" can be approved. A draft must "
                "first be completed and submitted by its member (My Profile > Submit for review).",
                messages.WARNING,
            )

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
        if count:
            self.message_user(request, f"Returned {count} profile(s) to their members.")

    def _back_to(self, object_id):
        return redirect(reverse("admin:profiles_profile_change", args=[object_id]))

    def _confirm_review(self, request, object_id, *, question, detail, button_label, button_variant, can_proceed, run,
                        images=()):
        """GET shows a confirmation page; only its POST (CSRF-protected) changes anything."""
        profile = self.get_object(request, object_id)
        if profile is None:
            return self._back_to(object_id)
        if request.method == "POST":
            if can_proceed:
                run(request, profile)
            return self._back_to(object_id)
        return confirmation_page(
            self, request, question=question, detail=detail, button_label=button_label, button_variant=button_variant,
            can_proceed=can_proceed, images=images,
            summary=f"{profile.profile_code} · {profile.display_name} · status: {profile.get_status_display()}",
            back_url=reverse("admin:profiles_profile_change", args=[profile.pk]),
        )

    @action(description="Approve profile", url_path="approve", permissions=["change"], variant=ActionVariant.SUCCESS)
    def approve_this(self, request, object_id):
        profile = self.get_object(request, object_id)
        pending = profile is not None and profile.status == ProfileStatus.PENDING_REVIEW
        return self._confirm_review(
            request, object_id,
            question="Approve this profile?" if pending else "This profile can't be approved yet",
            detail=(
                "It becomes visible to other members and the member is notified."
                if pending
                else "Only profiles with status \"Pending review\" can be approved. A draft must first be completed "
                "and submitted by its member (My Profile > Submit for review)."
            ),
            button_label="Yes, approve", button_variant="success", can_proceed=pending,
            run=lambda request, profile: self.approve(request, Profile.objects.filter(pk=profile.pk)),
        )

    @action(
        description="Request changes", url_path="request-changes", permissions=["change"], variant=ActionVariant.WARNING,
    )
    def request_changes_this(self, request, object_id):
        profile = self.get_object(request, object_id)
        ready = profile is not None and profile.status == ProfileStatus.PENDING_REVIEW and bool(profile.review_note)
        if profile is not None and profile.status != ProfileStatus.PENDING_REVIEW:
            detail = "Only profiles with status \"Pending review\" can be returned to their member."
        elif profile is not None and not profile.review_note:
            detail = "First write what needs changing in \"Review note\" on the profile page and save it."
        else:
            detail = f"The member is asked to update their profile and sees your note: “{profile.review_note}”"
        return self._confirm_review(
            request, object_id,
            question="Return this profile to its member?" if ready else "Changes can't be requested yet",
            detail=detail, button_label="Yes, request changes", button_variant="warning", can_proceed=ready,
            run=lambda request, profile: self.request_changes(request, Profile.objects.filter(pk=profile.pk)),
        )

    @action(description="Approve photos", url_path="approve-photos", permissions=["change"], variant=ActionVariant.PRIMARY)
    def approve_photos_this(self, request, object_id):
        profile = self.get_object(request, object_id)
        pending = list(profile.photos.filter(status=PhotoStatus.PENDING)) if profile else []

        def run(request, profile):
            count = review_photos(self, request, profile.photos.filter(status=PhotoStatus.PENDING), *PHOTO_APPROVED)
            self.message_user(request, f"Approved {count} photo(s). The member has been notified.")

        return self._confirm_review(
            request, object_id,
            question=f"Approve {len(pending)} photo(s) awaiting review?" if pending else "No photos are waiting for review",
            detail=(
                "Approved photos become visible to members, subject to the member's photo privacy setting. To turn "
                "a photo down instead, open it under Profile photos and use \"Reject photo\"."
                if pending
                else "This member has no photos with status \"Pending\"."
            ),
            button_label="Yes, approve all of these", button_variant="success", can_proceed=bool(pending), run=run,
            images=[signed_photo_url(photo) for photo in pending],
        )


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
    # The same review steps as buttons at the top of a photo's own page.
    actions_detail = ["approve_this", "reject_this"]

    def has_add_permission(self, request):
        return False  # photos are uploaded by members through the API, which validates them

    @admin.display(description="Photo")
    def preview(self, photo):
        return format_html('<img src="{}" alt="" style="height:72px;border-radius:4px">', signed_photo_url(photo))

    @admin.action(description="Approve selected photos", permissions=["change"])
    def approve(self, request, queryset):
        self.message_user(request, f"Approved {review_photos(self, request, queryset, *PHOTO_APPROVED)} photo(s).")

    @admin.action(description="Reject selected photos (add a review note to explain)", permissions=["change"])
    def reject(self, request, queryset):
        self.message_user(request, f"Rejected {review_photos(self, request, queryset, *PHOTO_REJECTED)} photo(s).")

    def _confirm_photo(self, request, object_id, *, outcome, question, detail, button_label, button_variant):
        """GET shows a confirmation page; only its POST (CSRF-protected) changes anything."""
        photo = self.get_object(request, object_id)
        back_url = reverse("admin:profiles_profilephoto_change", args=[object_id])
        if photo is None:
            return redirect(back_url)
        already = photo.status == outcome[0]
        if request.method == "POST":
            count = 0 if already else review_photos(self, request, ProfilePhoto.objects.filter(pk=photo.pk), *outcome)
            self.message_user(request, "Done. The member has been notified." if count else "Nothing changed.")
            return redirect(back_url)
        return confirmation_page(
            self, request, question=question, detail=detail, back_url=back_url, button_label=button_label,
            button_variant=button_variant, can_proceed=not already, images=[signed_photo_url(photo)],
            summary=f"Photo of {photo.profile.profile_code} · status: {photo.get_status_display()}",
        )

    @action(description="Approve photo", url_path="approve", permissions=["change"], variant=ActionVariant.SUCCESS)
    def approve_this(self, request, object_id):
        return self._confirm_photo(
            request, object_id, outcome=PHOTO_APPROVED, question="Approve this photo?",
            detail="It becomes visible to members, subject to the member's photo privacy setting.",
            button_label="Yes, approve", button_variant="success",
        )

    @action(description="Reject photo", url_path="reject", permissions=["change"], variant=ActionVariant.DANGER)
    def reject_this(self, request, object_id):
        return self._confirm_photo(
            request, object_id, outcome=PHOTO_REJECTED, question="Reject this photo?",
            detail="The member is told it wasn't approved. To explain why, write a Review note on this page and "
            "save it first.",
            button_label="Yes, reject", button_variant="danger",
        )
