from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.analytics import tasks
from apps.analytics.models import SystemLog


class TaskTests(TestCase):
    def test_prune_logs_keeps_recent(self):
        old = SystemLog.objects.create(message="old")
        SystemLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=45))
        SystemLog.objects.create(message="new")
        self.assertEqual(tasks.prune_system_logs.apply().get(), 1)
        self.assertEqual(list(SystemLog.objects.values_list("message", flat=True)), ["new"])

    def test_flush_tokens_runs(self):
        tasks.flush_expired_tokens.apply().get()

    def test_5xx_is_logged(self):
        from django.test import override_settings
        from apps.core.tests.helpers import client_for, make_user
        c = client_for(make_user())
        c.raise_request_exception = False
        from unittest import mock
        with mock.patch("apps.workspaces.views.WorkspaceSummaryView.get", side_effect=RuntimeError("boom")):
            self.assertEqual(c.get("/api/v1/workspace/summary/").status_code, 500)
        self.assertEqual(SystemLog.objects.filter(status_code=500).count(), 1)
