from django.db import models


class FurnitureTemplate(models.Model):
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=24)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    defaults = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name
