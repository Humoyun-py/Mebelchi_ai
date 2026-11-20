from .models import FeatureFlag, UsageEvent


def track(user, kind: str, **meta):
    try:
        UsageEvent.objects.create(user=user if getattr(user, "is_authenticated", False) else None, kind=kind, meta=meta)
    except Exception:  # analytics must never break a request
        pass


def feature_enabled(key: str, default: bool = True) -> bool:
    f = FeatureFlag.objects.filter(key=key).first()
    return f.enabled if f else default
