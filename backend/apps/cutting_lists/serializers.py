from django.db import transaction
from rest_framework import serializers

from .models import CuttingList, CuttingPart, OptimizationRun


class CuttingPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuttingPart
        fields = ["id", "name", "width", "height", "thickness", "quantity", "material", "can_rotate", "edge_w", "edge_h", "edge_note"]
        read_only_fields = ["id"]

    def validate(self, a):
        for k in ("width", "height"):
            if k in a and not 10 <= a[k] <= 6000:
                raise serializers.ValidationError({k: "Must be between 10 and 6000 mm."})
        if "thickness" in a and not 2 <= a["thickness"] <= 60:
            raise serializers.ValidationError({"thickness": "Must be between 2 and 60 mm."})
        if "quantity" in a and not 1 <= a["quantity"] <= 500:
            raise serializers.ValidationError({"quantity": "Must be between 1 and 500."})
        for k in ("edge_w", "edge_h"):
            if a.get(k, 0) > 2:
                raise serializers.ValidationError({k: "A part has at most 2 edges per direction."})
        return a


class CuttingListSerializer(serializers.ModelSerializer):
    parts = CuttingPartSerializer(many=True, required=False)
    totals = serializers.SerializerMethodField()
    latest_run = serializers.SerializerMethodField()

    class Meta:
        model = CuttingList
        fields = ["id", "name", "project", "sheet_length", "sheet_width", "kerf", "trim", "parts", "totals", "latest_run", "created_at", "updated_at"]
        read_only_fields = ["id", "totals", "latest_run", "created_at", "updated_at"]

    def get_totals(self, obj):
        parts = list(obj.parts.all())
        area = sum(float(p.width) * float(p.height) * p.quantity for p in parts) / 1e6
        edge = sum((p.edge_w * float(p.width) + p.edge_h * float(p.height)) * p.quantity for p in parts) / 1000
        return {"pieces": sum(p.quantity for p in parts), "area_m2": round(area, 4), "edge_banding_m": round(edge, 2)}

    def get_latest_run(self, obj):
        r = obj.runs.first()
        return {"id": r.id, "sheet_count": r.sheet_count, "utilization_pct": r.utilization_pct, "created_at": r.created_at} if r else None

    def validate_project(self, p):
        if p and p.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Project not found.")
        return p

    def validate(self, a):
        if "sheet_length" in a and not 300 <= a["sheet_length"] <= 6000:
            raise serializers.ValidationError({"sheet_length": "Must be between 300 and 6000 mm."})
        if "sheet_width" in a and not 300 <= a["sheet_width"] <= 3500:
            raise serializers.ValidationError({"sheet_width": "Must be between 300 and 3500 mm."})
        return a

    @transaction.atomic
    def create(self, data):
        parts = data.pop("parts", [])
        obj = CuttingList.objects.create(**data)
        CuttingPart.objects.bulk_create([CuttingPart(cutting_list=obj, **p) for p in parts])
        return obj

    @transaction.atomic
    def update(self, instance, data):
        parts = data.pop("parts", None)
        for k, v in data.items():
            setattr(instance, k, v)
        instance.save()
        if parts is not None:  # full replacement of the parts table
            instance.parts.all().delete()
            CuttingPart.objects.bulk_create([CuttingPart(cutting_list=instance, **p) for p in parts])
        return instance


class OptimizeParamsSerializer(serializers.Serializer):
    allow_rotation = serializers.BooleanField(default=True)


class FromCalculationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, required=False)
    project = serializers.IntegerField(required=False, allow_null=True)
    sheet_length = serializers.IntegerField(required=False, min_value=300, max_value=6000)
    sheet_width = serializers.IntegerField(required=False, min_value=300, max_value=3500)
    width = serializers.FloatField()
    height = serializers.FloatField()
    depth = serializers.FloatField()
    thickness = serializers.FloatField(default=18)
    shelves = serializers.IntegerField(default=0)
    doors = serializers.IntegerField(default=0)
    drawers = serializers.IntegerField(default=0)
    back_thickness = serializers.FloatField(default=4)
    material = serializers.CharField(default="MDF", max_length=20)
    back_material = serializers.CharField(default="HDF", max_length=20)


class OptimizationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptimizationRun
        fields = ["id", "sheet_count", "utilization_pct", "result", "created_at"]
