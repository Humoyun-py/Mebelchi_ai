from django.conf import settings
from django.db import models


class CuttingList(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cutting_lists")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="cutting_lists")
    name = models.CharField(max_length=160)
    sheet_length = models.PositiveIntegerField(default=2800)
    sheet_width = models.PositiveIntegerField(default=2070)
    kerf = models.DecimalField(max_digits=4, decimal_places=1, default=3)
    trim = models.DecimalField(max_digits=4, decimal_places=1, default=10)
    source_inputs = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class CuttingPart(models.Model):
    cutting_list = models.ForeignKey(CuttingList, on_delete=models.CASCADE, related_name="parts")
    name = models.CharField(max_length=120)
    width = models.DecimalField(max_digits=7, decimal_places=1)
    height = models.DecimalField(max_digits=7, decimal_places=1)
    thickness = models.DecimalField(max_digits=5, decimal_places=1)
    quantity = models.PositiveIntegerField(default=1)
    material = models.CharField(max_length=40, default="MDF")
    can_rotate = models.BooleanField(default=False)
    edge_w = models.PositiveSmallIntegerField(default=0)
    edge_h = models.PositiveSmallIntegerField(default=0)
    edge_note = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["id"]


class OptimizationRun(models.Model):
    cutting_list = models.ForeignKey(CuttingList, on_delete=models.CASCADE, related_name="runs")
    result = models.JSONField()
    sheet_count = models.PositiveIntegerField(default=0)
    utilization_pct = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
