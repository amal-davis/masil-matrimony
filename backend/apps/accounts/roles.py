from django.db import models


class Role(models.TextChoices):
    MEMBER = "member", "Matrimony member"
    SUPER_ADMIN = "super_admin", "Super administrator"
    ADMIN = "admin", "Administrator"
    VERIFICATION_STAFF = "verification_staff", "Profile verification staff"
    TELECALLER_MANAGER = "telecaller_manager", "Telecaller manager"
    TELECALLER = "telecaller", "Telecaller"
    CONTENT_MANAGER = "content_manager", "Content manager"


STAFF_ROLES = frozenset(Role.values) - {Role.MEMBER}
