"""`rooms` currently holds only the RoomFlow model. No view, serializer or URL uses it (the room chat runs on apps.conversations);
these tests pin down what the model guarantees so the planned room API can rely on it."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.tests.helpers import make_user
from apps.designs.models import Design
from apps.rooms.models import RoomFlow


class RoomFlowModelTests(TestCase):
    def setUp(self):
        self.u = make_user("a@x.com")

    def test_defaults(self):
        f = RoomFlow.objects.create(owner=self.u)
        self.assertEqual((f.status, f.step, f.answers, f.design_id, f.photo_id), ("active", "goal", {}, None, None))
        self.assertEqual(str(f), f"RoomFlow {f.pk} (active, goal)")

    def test_status_choices(self):
        self.assertEqual(set(RoomFlow.Status.values), {"active", "completed", "abandoned"})

    def test_deleting_the_owner_deletes_the_flows(self):
        RoomFlow.objects.create(owner=self.u)
        self.u.delete()
        self.assertEqual(RoomFlow.objects.count(), 0)

    def test_one_design_belongs_to_at_most_one_flow(self):
        d = Design.objects.create(owner=self.u, name="Room")
        RoomFlow.objects.create(owner=self.u, design=d)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RoomFlow.objects.create(owner=self.u, design=d)

    def test_deleting_the_design_keeps_the_conversation(self):
        d = Design.objects.create(owner=self.u, name="Room")
        f = RoomFlow.objects.create(owner=self.u, design=d, step="size", answers={"goal": "kitchen"})
        d.delete()
        f.refresh_from_db()
        self.assertEqual((f.design_id, f.step, f.answers), (None, "size", {"goal": "kitchen"}))

    def test_the_user_status_lookup_has_its_index(self):
        self.assertIn("roomflow_owner_status_idx", [i.name for i in RoomFlow._meta.indexes])

    def test_flows_are_listed_newest_first(self):
        a, b = RoomFlow.objects.create(owner=self.u), RoomFlow.objects.create(owner=self.u)
        RoomFlow.objects.filter(pk=a.pk).update(step="size")      # touches nothing but the row; updated_at is auto_now so use save
        a.refresh_from_db(); a.save()
        self.assertEqual(list(RoomFlow.objects.values_list("pk", flat=True)), [a.pk, b.pk])

    def test_there_is_no_public_api_yet(self):
        from django.urls import Resolver404, resolve
        for path in ("/api/v1/rooms/", "/api/v1/room-flows/"):
            with self.assertRaises(Resolver404):
                resolve(path)
