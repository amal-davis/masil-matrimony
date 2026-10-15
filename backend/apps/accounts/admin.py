from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserChangeForm, UserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ["-date_joined"]
    list_display = ["email", "phone_number", "full_name", "role", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "phone_number", "first_name", "last_name"]
    readonly_fields = ["public_id", "last_login", "date_joined"]

    fieldsets = [
        (None, {"fields": ["public_id", "email", "phone_number", "password"]}),
        ("Personal info", {"fields": ["first_name", "last_name"]}),
        ("Verification", {"fields": ["email_verified_at", "phone_verified_at"]}),
        (
            "Access",
            {"fields": ["role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions"]},
        ),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": ["email", "phone_number", "role", "password1", "password2"],
            },
        ),
    ]
