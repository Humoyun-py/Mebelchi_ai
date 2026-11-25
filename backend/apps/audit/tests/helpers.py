"""Audit rows can never be deleted (not by the ORM, not by raw SQL on PostgreSQL), so tests cannot "forget the setup noise" by
deleting. They mark a floor instead and look only at rows created after it."""
from apps.audit.models import AuditLog

_floor = [0]


def mark(test):
    """Hide every audit row that exists right now from `rows()`; the floor is reset when the test ends."""
    _floor[0] = AuditLog.objects.order_by("-id").values_list("id", flat=True).first() or 0
    test.addCleanup(lambda: _floor.__setitem__(0, 0))


def rows():
    return AuditLog.objects.filter(id__gt=_floor[0])
