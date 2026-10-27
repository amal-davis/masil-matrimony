"""
Write SQL that installs MySQL/MariaDB time-zone definitions (apps.core.mysql_timezones).

    .venv\\Scripts\\python manage.py timezone_sql --output tz.sql
    mariadb -u root -h 127.0.0.1 -P <port> mysql < tz.sql      (or mysql.exe for XAMPP's MySQL)
    then restart the database server

The app's own database account can't write the `mysql` schema; an administrator
loads the file. Only for servers whose time-zone tables are empty: it refuses
to overwrite unless --replace is given. Nothing in the project database changes.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.mysql_timezones import timezone_sql


class Command(BaseCommand):
    help = "Write SQL installing MySQL/MariaDB time-zone definitions from the tzdata package."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, help="File to write the SQL to.")
        parser.add_argument("--zone", action="append", default=[], help="Only these zones (repeatable).")
        parser.add_argument("--replace", action="store_true", help="Empty the time-zone tables first.")

    def handle(self, *args, **options):
        sql, included, skipped = timezone_sql(options["zone"] or None, replace=options["replace"])
        for required in {settings.TIME_ZONE, "UTC"}:
            if required not in included:
                raise CommandError(f"{required} couldn't be generated exactly; nothing was written.")
        with open(options["output"], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(sql)
        self.stdout.write(f"Wrote {len(included)} zones to {options['output']} (including {settings.TIME_ZONE} and UTC).")
        if skipped:
            self.stdout.write(f"Left out {len(skipped)} zones with daylight-saving rules or other limits, e.g. "
                              + ", ".join(name for name, _ in skipped[:5]) + ".")
