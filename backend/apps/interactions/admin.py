from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ContactView, Interest, Shortlist


@admin.register(Interest)
class InterestAdmin(ModelAdmin):
    """Read-only: interests are changed only by the members involved, through the API."""

    list_display = ["sender", "receiver", "status", "created_at", "responded_at"]
    list_filter = ["status", "created_at"]
    list_select_related = ["sender", "receiver"]
    search_fields = ["sender__profile_code", "receiver__profile_code"]
    search_help_text = "Search by the sender's or receiver's Matrimony ID."
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Shortlist)
class ShortlistAdmin(ModelAdmin):
    list_display = ["owner", "profile", "created_at"]
    list_select_related = ["owner", "profile"]
    search_fields = ["owner__profile_code", "profile__profile_code"]
    search_help_text = "Search by Matrimony ID."
    ordering = ["-created_at"]
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ContactView)
class ContactViewAdmin(ModelAdmin):
    """Read-only record of paid contact-number views. Lists Matrimony IDs, never the numbers."""

    list_display = ["viewer", "profile", "subscription", "created_at"]
    list_select_related = ["viewer", "profile", "subscription"]
    search_fields = ["viewer__profile_code", "profile__profile_code"]
    search_help_text = "Search by the viewer's or the viewed member's Matrimony ID."
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
