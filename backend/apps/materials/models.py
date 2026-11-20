from django.conf import settings
from django.db import models


class Material(models.Model):
    class Kind(models.TextChoices):
        MDF = "MDF", "MDF"
        LDSP = "LDSP", "Laminated chipboard (LDSP)"
        PLYWOOD = "PLYWOOD", "Plywood"
        HDF = "HDF", "HDF"
        SOLID = "SOLID", "Solid wood"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="materials")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    thickness = models.DecimalField(max_digits=5, decimal_places=1)
    sheet_length = models.PositiveIntegerField(default=2800)
    sheet_width = models.PositiveIntegerField(default=2070)
    price_per_sheet = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    color = models.CharField(max_length=7, default="#c9a27a")
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "thickness", "name"]

    def __str__(self):
        return f"{self.name} {self.thickness}mm"
