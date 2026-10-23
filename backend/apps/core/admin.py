"""
Site-wide admin registrations for the Django Unfold admin.

- Groups get Unfold styling. Staff permissions are managed with groups:
  see `python manage.py sync_admin_groups`.
- The JWT blacklist tables are removed from the admin: their pages would
  show full refresh tokens, which are credentials.
- Django's own audit log (LogEntry) is shown read-only to superusers.
"""
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from unfold.admin import ModelAdmin

for model in (OutstandingToken, BlacklistedToken):
    if admin.site.is_registered(model):
        admin.site.unregister(model)

admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    """Who changed what in the admin. Entries can't be added, edited or removed here."""

    list_display = ["action_time", "user", "content_type", "object_repr", "action_flag", "change_message"]
    list_filter = ["action_flag", "content_type"]
    list_select_related = ["user", "content_type"]
    search_fields = ["object_repr", "user__email", "change_message"]
    date_hierarchy = "action_time"
    ordering = ["-action_time"]
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
