from django.contrib import admin

from .models import AIUsage


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "feature", "provider", "model", "status", "input_tokens", "output_tokens", "user")
    list_filter = ("status", "provider", "feature")
    readonly_fields = [f.name for f in AIUsage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
