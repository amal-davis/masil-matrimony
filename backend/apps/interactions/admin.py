from django.contrib import admin

from .models import Interest, Shortlist


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    """Read-only: interests are changed only by the members involved, through the API."""

    list_display = ["sender", "receiver", "status", "created_at", "responded_at"]
    list_filter = ["status"]
    search_fields = ["sender__profile_code", "receiver__profile_code"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Shortlist)
class ShortlistAdmin(admin.ModelAdmin):
    list_display = ["owner", "profile", "created_at"]
    search_fields = ["owner__profile_code", "profile__profile_code"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
