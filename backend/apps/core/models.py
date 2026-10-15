"""Shared abstract model base classes. This app defines no database tables."""
from django.db import models


class TimeStampedModel(models.Model):
    """Adds created/updated timestamps to a model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
