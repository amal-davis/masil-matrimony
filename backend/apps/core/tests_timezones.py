"""
Time-zone definitions for MySQL/MariaDB (apps.core.mysql_timezones, the timezone_sql
command and the core.E001 database check), and the admin date drill-downs that
need them. Tests marked "MySQL" run only against the MySQL/MariaDB test database.
"""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone as dj_timezone

from apps.accounts.roles import Role
from apps.interactions.models import Interest
from apps.profiles.test_utils import make_profile, make_user

from . import checks, mysql_timezones

on_mysql = unittest.skipUnless(connection.vendor == "mysql", "needs the MySQL/MariaDB test database")


class TimezoneDataTests(TestCase):
    def test_india_and_utc_are_exact(self):
        india = mysql_timezones.parse("Asia/Kolkata")
        mysql_timezones.verify(india)
        current = india.types[india.transitions[-1][1]]
        self.assertEqual(current, (19800, 0, "IST"))  # +05:30, no daylight saving
        utc = mysql_timezones.parse("UTC")
        self.assertEqual((utc.transitions, utc.types), ([], [(0, 0, "UTC")]))

    def test_zones_with_daylight_saving_rules_are_left_out(self):
        with self.assertRaises(mysql_timezones.Unsupported):
            mysql_timezones.parse("America/New_York")
        sql, included, skipped = mysql_timezones.timezone_sql(["Asia/Kolkata", "UTC", "America/New_York"])
        self.assertEqual(included, ["Asia/Kolkata", "UTC"])
        self.assertEqual([name for name, _ in skipped], ["America/New_York"])
        self.assertNotIn("TRUNCATE", sql)  # never overwrites unless asked

    def test_command_writes_the_project_zones(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tz.sql"
            call_command("timezone_sql", "--output", str(path), "--zone", "Asia/Kolkata", "--zone", "UTC", stdout=None)
            text = path.read_text(encoding="utf-8")
        self.assertIn("VALUES ('Asia/Kolkata', @time_zone_id)", text)
        self.assertIn("(@time_zone_id,3,19800,0,'IST')", text)


@on_mysql
class MySQLTimezoneTests(TestCase):
    """Against the real MySQL/MariaDB server the project uses."""

    def test_the_server_converts_between_utc_and_india(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT CONVERT_TZ('2026-10-27 18:45:00', 'UTC', 'Asia/Kolkata')")
            self.assertEqual(cursor.fetchone()[0], datetime(2026, 10, 28, 0, 15))
        self.assertEqual(checks.mysql_time_zones(None, databases=["default"]), [])

    @override_settings(TIME_ZONE="America/New_York")
    def test_the_check_reports_a_zone_the_server_doesnt_know(self):
        errors = checks.mysql_time_zones(None, databases=["default"])
        self.assertEqual([error.id for error in errors], ["core.E001"])


class InterestAdminDateDrillDownTests(TestCase):
    """The page that failed: its date_hierarchy runs CONVERT_TZ on MySQL/MariaDB."""

    def test_list_and_drill_down_by_indian_date(self):
        groom, bride = make_profile(gender="male"), make_profile(gender="female")
        interest = Interest.objects.create(sender=groom, receiver=bride)
        # 20:00 UTC on 26 October is 01:30 on 27 October in India: the drill-down must use India's date.
        Interest.objects.filter(pk=interest.pk).update(created_at=datetime(2026, 10, 26, 20, 0, tzinfo=timezone.utc))
        self.client.force_login(make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True))
        url = reverse("admin:interactions_interest_changelist")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(list(Interest.objects.datetimes("created_at", "day")),
                         [datetime(2026, 10, 27, tzinfo=dj_timezone.get_current_timezone())])
        day = self.client.get(url, {"created_at__year": 2026, "created_at__month": 10, "created_at__day": 27})
        self.assertEqual(day.status_code, 200)
        self.assertEqual(list(day.context["cl"].result_list), [interest])
        self.assertEqual(self.client.get(url, {"created_at__day": 26, "created_at__month": 10,
                                               "created_at__year": 2026}).context["cl"].result_count, 0)
        for other in ("admin:interactions_contactview_changelist", "admin:enquiries_enquiry_changelist"):
            self.assertEqual(self.client.get(reverse(other)).status_code, 200)
        self.assertEqual(Interest.objects.get().created_at, datetime(2026, 10, 26, 20, 0, tzinfo=timezone.utc))
