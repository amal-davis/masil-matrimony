from django.contrib import admin

from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone", "status", "assigned_to", "created_at"]
    list_filter = ["status", "source", "created_at"]
    search_fields = ["name", "email", "phone"]
    date_hierarchy = "created_at"
    # What the visitor sent stays as they sent it; staff only manage handling.
    readonly_fields = ["public_id", "name", "email", "phone", "message", "source", "created_at", "updated_at"]
    autocomplete_fields = ["assigned_to", "converted_user"]

    fieldsets = [
        (None, {"fields": ["public_id", "name", "email", "phone", "message", "source"]}),
        ("Handling", {"fields": ["status", "assigned_to", "converted_user"]}),
        ("Dates", {"fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return False
