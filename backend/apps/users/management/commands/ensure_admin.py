"""Create or update the site administrator from environment variables.

Used on hosts without a shell (Render free plan): set ADMIN_EMAIL and ADMIN_PASSWORD and the start script runs this command.
Nothing happens when they are not set. An existing account with that email is promoted to superuser; its password is only
changed when ADMIN_RESET_PASSWORD=1, so a restart never overwrites a password the admin changed."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password


class Command(BaseCommand):
    help = "Create/promote the administrator from ADMIN_EMAIL and ADMIN_PASSWORD (no-op when unset)."

    def handle(self, *a, **o):
        email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD") or ""
        if not email or not password:
            self.stdout.write("ensure_admin: ADMIN_EMAIL/ADMIN_PASSWORD not set, skipping")
            return
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            try:
                validate_password(password)
            except ValidationError as e:
                raise CommandError("ADMIN_PASSWORD rejected: " + " ".join(e.messages)) from e
            user = User.objects.create_superuser(email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"ensure_admin: created administrator {email}"))
            return
        changed = []
        if not (user.is_staff and user.is_superuser):
            user.is_staff = user.is_superuser = True
            changed.append("promoted")
        if os.environ.get("ADMIN_RESET_PASSWORD") == "1":
            user.set_password(password)
            changed.append("password reset")
        if changed:
            user.save()
        self.stdout.write(f"ensure_admin: {email} {', '.join(changed) or 'already an administrator'}")
