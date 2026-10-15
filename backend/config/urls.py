from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("config.api_v1")),
]

handler404 = "apps.core.exceptions.json_not_found"
handler500 = "apps.core.exceptions.json_server_error"
