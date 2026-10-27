"""
Keep stored recommendations honest when the data behind them changes: a saved
profile or partner preference marks the affected recommendations stale, and a
preference change regenerates that member's recommendations once the save is
committed (MATCH_REGENERATE_ON_CHANGE). The member's own Matches page is always
computed live, so it never shows a stale result.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.profiles.models import PartnerPreference, Profile

from . import engine

logger = logging.getLogger(__name__)
RELEVANT_PROFILE_FIELDS = {*engine.PROFILE_FIELDS, "status", "visibility"}


@receiver(post_save, sender=Profile, dispatch_uid="matchmaking_profile_saved")
def profile_saved(sender, instance, created, update_fields=None, raw=False, **kwargs):
    if raw or created or (update_fields is not None and not RELEVANT_PROFILE_FIELDS & set(update_fields)):
        return
    engine.mark_stale(member=instance)
    engine.mark_stale(candidate=instance)


def _regenerate(profile_id):
    profile = Profile.objects.filter(pk=profile_id).first()
    if profile is None:  # deleted in the same transaction (e.g. clear_member_data)
        return
    try:
        engine.generate_for(profile)
    except Exception:  # noqa: BLE001 - the member's save already succeeded; the stale marks stay
        logger.exception("Regenerating matches after a preference change failed for profile %s", profile_id)


@receiver(post_save, sender=PartnerPreference, dispatch_uid="matchmaking_preference_saved")
@receiver(post_delete, sender=PartnerPreference, dispatch_uid="matchmaking_preference_deleted")
def preference_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    engine.mark_stale(member_id=instance.profile_id)
    if settings.MATCH_REGENERATE_ON_CHANGE and kwargs.get("signal") is post_save:
        profile_id = instance.profile_id
        transaction.on_commit(lambda: _regenerate(profile_id))
