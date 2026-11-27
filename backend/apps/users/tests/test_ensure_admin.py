import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

User = get_user_model()
GOOD = "Str0ng-admin-pass-2026"


def run(**env):
    out = io.StringIO()
    with mock.patch.dict("os.environ", env, clear=False):
        call_command("ensure_admin", stdout=out)
    return out.getvalue()


class EnsureAdminTests(TestCase):
    def test_does_nothing_without_variables(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            out = io.StringIO()
            call_command("ensure_admin", stdout=out)
        self.assertIn("skipping", out.getvalue())
        self.assertFalse(User.objects.exists())

    def test_creates_a_superuser(self):
        run(ADMIN_EMAIL="Boss@Example.com", ADMIN_PASSWORD=GOOD)
        u = User.objects.get()
        self.assertEqual(u.email, "boss@example.com")
        self.assertTrue(u.is_staff and u.is_superuser)
        self.assertTrue(u.check_password(GOOD))

    def test_weak_password_is_refused(self):
        with self.assertRaises(CommandError):
            run(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="123")
        self.assertFalse(User.objects.exists())

    def test_existing_user_is_promoted_but_keeps_its_password(self):
        User.objects.create_user(email="boss@example.com", password="Old-pass-for-user-1")
        run(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD=GOOD)
        u = User.objects.get()
        self.assertTrue(u.is_superuser)
        self.assertTrue(u.check_password("Old-pass-for-user-1"))

    def test_restart_never_overwrites_a_changed_password(self):
        run(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD=GOOD)
        u = User.objects.get()
        u.set_password("Changed-by-admin-77")
        u.save()
        run(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD=GOOD)
        self.assertTrue(User.objects.get().check_password("Changed-by-admin-77"))

    def test_reset_flag_sets_the_password(self):
        run(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD=GOOD)
        run(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="Another-Str0ng-pass-9", ADMIN_RESET_PASSWORD="1")
        self.assertTrue(User.objects.get().check_password("Another-Str0ng-pass-9"))
