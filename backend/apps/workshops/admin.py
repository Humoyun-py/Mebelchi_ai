from django.contrib import admin

from .models import Order, Task, Workshop, WorkshopMember


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    """Platform staff suspend or reactivate a workshop here (the API cannot set `suspended`)."""

    list_display = ("name", "slug", "owner", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "slug", "owner__email")
    readonly_fields = ("slug", "order_counter")


@admin.register(WorkshopMember)
class WorkshopMemberAdmin(admin.ModelAdmin):
    list_display = ("workshop", "user", "role", "status")
    list_filter = ("role", "status")
    search_fields = ("user__email", "workshop__name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "workshop", "title", "status", "payment_status")
    list_filter = ("status", "payment_status")
    search_fields = ("order_number", "title", "customer_name")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "workshop", "status", "priority", "deadline")
    list_filter = ("status", "priority")
