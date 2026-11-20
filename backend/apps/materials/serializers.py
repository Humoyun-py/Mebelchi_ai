from rest_framework import serializers

from .models import Material


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "name", "kind", "thickness", "sheet_length", "sheet_width", "price_per_sheet", "color", "is_system"]
        read_only_fields = ["id", "is_system"]

    def validate_thickness(self, v):
        if not 2 <= v <= 60:
            raise serializers.ValidationError("Thickness must be between 2 and 60 mm.")
        return v

    def validate(self, a):
        for k in ("sheet_length", "sheet_width"):
            if k in a and not 300 <= a[k] <= 6000:
                raise serializers.ValidationError({k: "Must be between 300 and 6000 mm."})
        return a
