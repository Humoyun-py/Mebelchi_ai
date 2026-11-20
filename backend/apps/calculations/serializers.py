from rest_framework import serializers

from .models import Calculation


class CabinetInputSerializer(serializers.Serializer):
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
    save = serializers.BooleanField(default=False, write_only=True)
    name = serializers.CharField(required=False, max_length=160, write_only=True)
    project = serializers.IntegerField(required=False, allow_null=True, write_only=True)


class CalculationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calculation
        fields = ["id", "name", "kind", "project", "inputs", "result", "created_at"]
        read_only_fields = fields
