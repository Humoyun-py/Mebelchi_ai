from django.contrib import admin, messages

from . import services
from .models import AppRelease


@admin.register(AppRelease)
class AppReleaseAdmin(admin.ModelAdmin):
    """Builds are added with `manage.py publish_android_release` (it computes the checksum from the file). Here an administrator publishes,
    unpublishes and edits the release notes. The file, version and checksum can never be edited."""

    list_display = ("version_name", "version_code", "channel", "is_published", "size_bytes", "download_count", "published_at", "created_at")
    list_filter = ("channel", "is_published")
    readonly_fields = [f.name for f in AppRelease._meta.fields if f.name not in ("notes", "is_published")]
    fields = ["platform", "channel", "version_name", "version_code", "apk", "sha256", "size_bytes", "notes", "is_published", "published_at", "download_count", "created_at"]
    actions = ["publish", "unpublish"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and "is_published" in form.changed_data and obj.is_published:
            try:
                obj.is_published = False
                obj.save(update_fields=["is_published"])
                services.publish_release(obj)
            except services.ReleaseError as e:
                messages.error(request, str(e))
            return
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected releases")
    def publish(self, request, queryset):
        for rel in queryset.order_by("version_code"):
            try:
                services.publish_release(rel)
            except services.ReleaseError as e:
                messages.error(request, f"{rel}: {e}")

    @admin.action(description="Unpublish selected releases")
    def unpublish(self, request, queryset):
        for rel in queryset:
            services.unpublish_release(rel)
