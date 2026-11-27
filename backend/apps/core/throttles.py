from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"


class ExportRateThrottle(UserRateThrottle):
    scope = "export"


class SmsRateThrottle(UserRateThrottle):
    """Every SMS costs money: a few per user per hour (the per-day cap is enforced in the phone-verification service)."""

    scope = "sms"
