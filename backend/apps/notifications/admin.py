from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ["recipient", "kind", "title", "created_at", "read_at"]
    list_filter = ["kind", "created_at"]
    list_select_related = ["recipient"]
    search_fields = ["recipient__email", "recipient__profile__profile_code"]
    search_help_text = "Search by the member's email or Matrimony ID."
    ordering = ["-created_at"]
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
