from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    """Same `?ordering=` contract, but rows without a value (e.g. no deadline) always sort last in both directions, and ties are
    broken by id so pagination is stable. Without this SQLite and PostgreSQL would disagree about where NULLs go."""

    def filter_queryset(self, request, queryset, view):
        fields = self.get_ordering(request, queryset, view)
        if not fields:
            return queryset
        exprs = [F(f.lstrip("-")).desc(nulls_last=True) if f.startswith("-") else F(f).asc(nulls_last=True) for f in fields]
        exprs.append(F("pk").desc() if fields[0].startswith("-") else F("pk").asc())
        return queryset.order_by(*exprs)
