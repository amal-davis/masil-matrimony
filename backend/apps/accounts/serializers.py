from rest_framework import serializers

from .models import User


class CurrentUserSerializer(serializers.ModelSerializer):
    """The signed-in user's own account. Never used for other users."""

    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "role",
            "email_verified_at",
            "phone_verified_at",
            "date_joined",
        ]
        read_only_fields = fields
