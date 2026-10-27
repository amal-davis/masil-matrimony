"""
Generate or refresh match recommendations (apps.matchmaking.engine).

    manage.py generate_matches                 # members with stale recommendations, and members never evaluated
    manage.py generate_matches --all           # every eligible member
    manage.py generate_matches --member MM482913 --member MM100200

Idempotent: running it again never duplicates anything. There is no task queue
in this project, so schedule it with Windows Task Scheduler or cron, e.g. nightly:

    cd <backend> && .venv\\Scripts\\python manage.py generate_matches
"""
from django.core.management.base import BaseCommand, CommandError

from apps.matchmaking import engine
from apps.matchmaking.models import MatchRecommendation, RecommendationStatus


class Command(BaseCommand):
    help = "Generate or refresh partner-preference match recommendations."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Every eligible member.")
        parser.add_argument("--member", action="append", default=[], help="A Matrimony ID (repeatable).")
        parser.add_argument("--limit", type=int, default=0, help="At most this many members (0 = no limit).")
        parser.add_argument("--batch-size", type=int, default=200)

    def handle(self, *args, **options):
        members = engine.eligible_members()
        if options["member"]:
            codes = [code.upper() for code in options["member"]]
            members = members.filter(profile_code__in=codes)
            if not members.exists():
                raise CommandError("No approved member with those Matrimony IDs.")
        elif not options["all"]:
            stale = MatchRecommendation.objects.filter(status=RecommendationStatus.STALE).values("member_id")
            evaluated = MatchRecommendation.objects.values("member_id")
            members = members.filter(pk__in=stale) | members.exclude(pk__in=evaluated)
        if options["limit"]:
            members = members.filter(pk__in=list(members.order_by("pk").values_list("pk", flat=True)[: options["limit"]]))
        record = engine.run(members, "command", batch_size=options["batch_size"])
        self.stdout.write(
            f"Evaluated {record.members_evaluated} member(s): {record.created} new, {record.updated} updated, "
            f"{record.unchanged} unchanged, {record.withdrawn} no longer matches, {record.failures} failed."
        )
        if record.failures:
            raise CommandError(f"{record.failures} member(s) failed; see the log.")
