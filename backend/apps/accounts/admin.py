from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm

from .forms import UserChangeForm, UserCreationForm
from .models import User

# Fields that grant admin access or permissions. Only superusers may change them,
# so a staff member with "change user" permission can't promote themselves or others.
PRIVILEGE_FIELDS = ["is_staff", "is_superuser", "groups", "user_permissions"]


class EmailVerifiedFilter(admin.SimpleListFilter):
    title = "email verified"
    parameter_name = "email_verified"

    def lookups(self, request, model_admin):
        return [("yes", "Verified"), ("no", "Not verified")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(email_verified_at=None)
        if self.value() == "no":
            return queryset.filter(email_verified_at=None)
        return queryset


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    ordering = ["-date_joined"]
    list_display = [
        "email", "matrimony_id", "phone_number", "full_name", "role", "email_verified", "is_active", "date_joined",
    ]
    list_filter = ["role", EmailVerifiedFilter, "is_active", "is_staff"]
    list_select_related = ["profile"]
    # Members are easiest to find by Matrimony ID, name or email.
    search_fields = ["email", "phone_number", "first_name", "last_name", "profile__profile_code", "profile__display_name"]
    search_help_text = "Search by email, mobile number, name or Matrimony ID."
    readonly_fields = ["public_id", "matrimony_id", "last_login", "date_joined"]
    list_per_page = 50

    fieldsets = [
        (None, {"fields": ["public_id", "email", "phone_number", "password"]}),
        ("Personal info", {"fields": ["first_name", "last_name", "matrimony_id"]}),
        ("Verification", {"fields": ["email_verified_at", "phone_verified_at"]}),
        ("Access", {"fields": ["role", "is_active", *PRIVILEGE_FIELDS]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                # "usable_password" lets staff create a member without a password: they set one
                # themselves with "Forgot password?" on the website.
                "fields": ["email", "phone_number", "role", "usable_password", "password1", "password2"],
            },
        ),
    ]

    @admin.display(description="Matrimony ID", ordering="profile__profile_code")
    def matrimony_id(self, user):
        profile = getattr(user, "profile", None)
        if profile is None:
            return "—"
        url = reverse("admin:profiles_profile_change", args=[profile.pk])
        return format_html('<a href="{}">{}</a>', url, profile.profile_code)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            # Verifying an address is the member's job (the emailed link); only superusers may override it.
            fields += [*PRIVILEGE_FIELDS, "email_verified_at"]
        return fields

    @admin.display(description="Email verified", boolean=True, ordering="email_verified_at")
    def email_verified(self, user):
        return user.email_verified_at is not None

    def has_change_permission(self, request, obj=None):
        # Only superusers may edit a superuser's account (password, email, flags).
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
