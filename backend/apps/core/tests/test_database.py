from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase

from apps.core.tests.helpers import client_for, make_user
from config.database import DatabaseStatus, resolve_database

BASE = Path("/srv/mebelchi/backend")
PG_ENV = {
    "POSTGRES_DB": "mebelchi_db",
    "POSTGRES_USER": "mebelchi_user",
    "POSTGRES_PASSWORD": "super-secret-pass",
    "POSTGRES_HOST": "db.internal",
    "POSTGRES_PORT": "5433",
}


def reachable(_pg):
    return None


def unreachable(_pg):
    return "OperationalError"


class DatabaseResolutionTests(SimpleTestCase):
    def test_no_postgres_name_uses_sqlite_without_probing(self):
        def boom(_pg):
            raise AssertionError("probe must not run for SQLite")
        cfg, status = resolve_database({}, BASE, probe=boom)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(cfg["NAME"], BASE / "db.sqlite3")
        self.assertEqual(status.active_engine, "sqlite")
        self.assertFalse(status.fallback_active)

    def test_sqlite_path_relative_and_absolute(self):
        cfg, _ = resolve_database({"DB_ENGINE": "sqlite", "SQLITE_PATH": "data/x.db"}, BASE)
        self.assertEqual(cfg["NAME"], BASE / "data/x.db")
        cfg, _ = resolve_database({"DB_ENGINE": "sqlite", "SQLITE_PATH": "/var/lib/x.db"}, BASE)
        self.assertEqual(cfg["NAME"], Path("/var/lib/x.db"))

    def test_postgres_used_when_reachable(self):
        cfg, status = resolve_database(PG_ENV, BASE, probe=reachable)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(cfg["HOST"], "db.internal")
        self.assertEqual(cfg["PORT"], "5433")
        self.assertEqual(status.active_engine, "postgresql")
        self.assertFalse(status.fallback_active)

    def test_unreachable_postgres_with_fallback_enabled_uses_sqlite(self):
        env = {**PG_ENV, "DATABASE_FALLBACK_ENABLED": "true"}
        cfg, status = resolve_database(env, BASE, probe=unreachable)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.sqlite3")
        self.assertTrue(status.fallback_active)
        self.assertEqual(status.configured_engine, "postgresql")
        self.assertEqual(status.connectivity_error, "OperationalError")

    def test_unreachable_postgres_without_fallback_refuses_to_start(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            resolve_database(PG_ENV, BASE, probe=unreachable)
        self.assertIn("DATABASE_FALLBACK_ENABLED", str(ctx.exception))

    def test_fallback_is_off_by_default(self):
        with self.assertRaises(ImproperlyConfigured):
            resolve_database(PG_ENV, BASE, probe=unreachable)

    def test_postgres_error_message_never_contains_password(self):
        def leaky(pg):
            return f"failed for {pg['USER']}"  # the probe receives the password; the message must not echo it
        env = {**PG_ENV, "DATABASE_FALLBACK_ENABLED": "1"}
        _, status = resolve_database(env, BASE, probe=leaky)
        self.assertNotIn("super-secret-pass", str(status.as_dict()))
        with self.assertRaises(ImproperlyConfigured) as ctx:
            resolve_database(PG_ENV, BASE, probe=leaky)
        self.assertNotIn("super-secret-pass", str(ctx.exception))

    def test_explicit_postgres_without_name_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            resolve_database({"DB_ENGINE": "postgresql"}, BASE, probe=reachable)

    def test_unknown_engine_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            resolve_database({"DB_ENGINE": "mysql"}, BASE)

    def test_status_dict_is_serialisable(self):
        status = DatabaseStatus("postgresql", "sqlite", True, True, "OperationalError")
        self.assertEqual(status.as_dict()["active_engine"], "sqlite")


class SystemStatusTests(TestCase):
    def setUp(self):
        self.user = make_user("u@x.com")
        self.admin = make_user("admin@x.com", is_staff=True, is_superuser=True)

    def test_status_requires_platform_admin(self):
        self.assertEqual(client_for(self.user).get("/api/v1/admin-api/system/").status_code, 403)

    def test_status_reports_database_and_services_without_secrets(self):
        r = client_for(self.admin).get("/api/v1/admin-api/system/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["backend"]["status"], "ok")
        expected = "postgresql" if settings.DATABASE_STATUS.active_engine == "postgresql" else "sqlite"
        self.assertEqual(r.data["database"]["vendor"], expected)
        self.assertTrue(r.data["database"]["connected"])
        self.assertEqual(r.data["database"]["active_engine"], expected)
        self.assertEqual(r.data["redis"]["status"], "not_configured")
        self.assertEqual(r.data["celery"]["status"], "eager")
        self.assertNotIn("password", str(r.data).lower())
