from django.urls import path

from .views import StoryDetailView, StoryImageView, StoryListView

app_name = "website_content"

urlpatterns = [
    path("", StoryListView.as_view(), name="stories"),
    # Before "<slug>/", which would otherwise match "images".
    path("images/<uuid:public_id>/", StoryImageView.as_view(), name="story-image"),
    path("<slug:slug>/", StoryDetailView.as_view(), name="story"),
]
