"""
Database check (run with `manage.py check --database default`): on MySQL/MariaDB
with USE_TZ, the server must know the named time zones Django converts between,
or date drill-downs in the admin fail (apps.core.mysql_timezones explains).
"""
from django.conf import settings
from django.core.checks import Error, Tags, register
from django.db import connections


@register(Tags.database)
def mysql_time_zones(app_configs, databases=None, **kwargs):
    errors = []
    for alias in databases or []:
        connection = connections[alias]
        if connection.vendor != "mysql" or not settings.USE_TZ:
            continue
        with connection.cursor() as cursor:
            cursor.execute("SELECT CONVERT_TZ('2000-01-01 00:00:00', 'UTC', %s)", [settings.TIME_ZONE])
            converted = cursor.fetchone()[0]
        if converted is None:
            errors.append(Error(
                f"The database server ({alias}) has no time-zone definitions for UTC and {settings.TIME_ZONE}.",
                hint="Admin date drill-downs and date truncation will fail. Run `manage.py timezone_sql --output tz.sql`, "
                     "load tz.sql into the `mysql` schema as an administrator, then restart the server.",
                id="core.E001",
            ))
    return errors
