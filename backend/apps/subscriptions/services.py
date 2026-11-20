from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Payment, Plan, Subscription
from .seed_data import PLANS


def free_plan() -> Plan:
    plan = Plan.objects.filter(slug="free").first()
    if plan:
        return plan
    d = dict(PLANS[0])
    slug = d.pop("slug")
    return Plan.objects.create(slug=slug, **d)


def ensure_subscription(user) -> Subscription:
    sub = getattr(user, "subscription", None) or Subscription.objects.filter(user=user).select_related("plan").first()
    if sub:
        return sub
    return Subscription.objects.create(user=user, plan=free_plan())


def usage(user) -> dict:
    from apps.files.services import storage_summary
    from apps.analytics.models import UsageEvent
    sub = ensure_subscription(user)
    plan = sub.plan
    st = storage_summary(user)
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    exports = UsageEvent.objects.filter(user=user, kind__startswith="export", created_at__gte=month_start).count()
    projects = user.projects.filter(status="active").count()
    return {
        "plan": {"slug": plan.slug, "name": plan.name, "price_usd": str(plan.price_usd), "features": plan.features},
        "status": sub.status,
        "projects": {"used": projects, "limit": plan.max_projects or None},
        "exports_this_month": {"used": exports, "limit": plan.max_exports_per_month or None},
        "storage": st,
    }


def enforce_project_limit(user):
    plan = ensure_subscription(user).plan
    if plan.max_projects and user.projects.filter(status="active").count() >= plan.max_projects:
        raise PermissionDenied(f"Your {plan.name} plan allows {plan.max_projects} active projects. Upgrade or archive a project.")


def enforce_export_limit(user):
    from apps.analytics.models import UsageEvent
    plan = ensure_subscription(user).plan
    if plan.max_exports_per_month:
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        n = UsageEvent.objects.filter(user=user, kind__startswith="export", created_at__gte=month_start).count()
        if n >= plan.max_exports_per_month:
            raise PermissionDenied(f"Monthly export limit of {plan.max_exports_per_month} reached for the {plan.name} plan.")


def enforce_storage_limit(user, extra_bytes: int):
    from apps.files.services import storage_summary
    plan = ensure_subscription(user).plan
    st = storage_summary(user)
    if st["used_bytes"] + extra_bytes > plan.storage_mb * 1024 * 1024:
        raise PermissionDenied(f"Storage limit of {plan.storage_mb} MB reached for the {plan.name} plan.")


def request_upgrade(user, plan: Plan) -> dict:
    sub = ensure_subscription(user)
    if plan.price_usd == 0:
        sub.plan, sub.status = plan, Subscription.Status.ACTIVE
        sub.save()
        return {"activated": True, "payment": None}
    payment = Payment.objects.create(user=user, plan=plan, amount=plan.price_usd)
    return {"activated": False, "payment_id": payment.id,
            "detail": "Upgrade requested. Online payment is not integrated yet; an administrator will confirm your payment and activate the plan."}


def confirm_payment(payment: Payment) -> Payment:
    payment.status = Payment.Status.PAID
    payment.confirmed_at = timezone.now()
    payment.save()
    sub = ensure_subscription(payment.user)
    sub.plan, sub.status = payment.plan, Subscription.Status.ACTIVE
    sub.save()
    return payment
