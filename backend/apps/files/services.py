from django.db.models import Sum


def storage_summary(user) -> dict:
    from apps.galleries.models import GalleryImage
    from apps.subscriptions.services import ensure_subscription
    img = GalleryImage.objects.filter(owner=user).aggregate(s=Sum("size_bytes"))
    doc = user.files.aggregate(s=Sum("size_bytes"))
    used = (img["s"] or 0) + (doc["s"] or 0)
    limit = ensure_subscription(user).plan.storage_mb * 1024 * 1024
    return {"used_bytes": used, "limit_bytes": limit, "percent": round(100 * used / limit, 2) if limit else 0,
            "images": GalleryImage.objects.filter(owner=user).count(), "files": user.files.count(),
            "images_bytes": img["s"] or 0, "files_bytes": doc["s"] or 0}
