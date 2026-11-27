from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.validators import validate_image


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role_selected=True)
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        MAKER = "maker", "Furniture Maker"
        HOMEOWNER = "homeowner", "Home Owner"
        # Workshops are onboarded and approved by an administrator; users cannot pick this role themselves.
        WORKSHOP = "workshop", "Furniture Workshop"

    SELF_SELECTABLE_ROLES = (Role.MAKER, Role.HOMEOWNER)

    class Theme(models.TextChoices):
        DARK = "dark", "Dark"
        LIGHT = "light", "Light"

    class Language(models.TextChoices):
        EN = "en", "English"
        UZ = "uz", "Uzbek"
        RU = "ru", "Russian"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=32, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    avatar = models.ImageField(upload_to="avatars/", blank=True, validators=[validate_image])
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.HOMEOWNER)
    role_selected = models.BooleanField(default=False)
    theme = models.CharField(max_length=8, choices=Theme.choices, default=Theme.DARK)
    language = models.CharField(max_length=4, choices=Language.choices, default=Language.EN)
    notify_email = models.BooleanField(default=True)
    notify_system = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ["-date_joined"]
        constraints = [
            # a phone number proves one account only; unverified numbers may repeat, verified ones may not
            models.UniqueConstraint(fields=["phone"], condition=models.Q(phone_verified_at__isnull=False), name="user_verified_phone_unique"),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class PhoneVerification(models.Model):
    """One SMS code sent to prove that a user controls a phone number. Only a keyed hash of the code is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="phone_verifications")
    phone = models.CharField(max_length=12)                     # normalised 998XXXXXXXXX
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)       # set when confirmed, superseded by a newer code, or locked out
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"], name="phoneverif_user_idx")]
