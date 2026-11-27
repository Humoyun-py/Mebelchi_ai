from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Read-only: provider transactions are created and changed only by verified webhooks."""

    list_display = ("created_at", "provider", "external_id", "order", "amount_minor", "currency", "status")
    list_filter = ("provider", "status")
    search_fields = ("external_id", "order__order_number")
    readonly_fields = [f.name for f in PaymentTransaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
