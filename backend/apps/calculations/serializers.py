from rest_framework import serializers

from . import engine
from .models import Calculation


class PriceListSerializer(serializers.Serializer):
    """Prices are always supplied by the caller or read from the user's material catalogue; the engine never invents one."""

    currency = serializers.CharField(max_length=8, required=False, allow_blank=True, default="")
    board_price_per_m2 = serializers.DictField(child=serializers.FloatField(min_value=0), required=False, default=dict,
                                               help_text='e.g. {"MDF 18": 95000, "HDF": 30000}; key = material or "material thickness"')
    waste_factor = serializers.FloatField(min_value=0, max_value=0.6, required=False, default=0.15)
    edge_price_per_m = serializers.FloatField(min_value=0, required=False, allow_null=True, default=None)
    edge_allowance = serializers.FloatField(min_value=0, max_value=0.5, required=False, default=0.05)
    hardware_prices = serializers.DictField(child=serializers.FloatField(min_value=0), required=False, default=dict,
                                            help_text='unit price per hardware name, e.g. {"Hinge": 12000}')
    labor_per_m2 = serializers.FloatField(min_value=0, required=False, allow_null=True, default=None)
    markup_pct = serializers.FloatField(min_value=0, max_value=300, required=False, default=0)


class CabinetFieldsSerializer(serializers.Serializer):
    """Engine parameters shared by every endpoint that takes a cabinet. New fields are optional and default to the old behaviour."""

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
    cabinet_type = serializers.ChoiceField(choices=engine.CABINET_TYPES, default="standard")
    edge_thickness = serializers.FloatField(default=0, help_text="mm of edge tape; 0 = cut sizes equal finished sizes")
    plinth_height = serializers.FloatField(default=100, help_text="kitchen_base only")
    sliding_overlap = serializers.FloatField(default=30, help_text="sliding_wardrobe only")
    track_top = serializers.FloatField(default=35, help_text="sliding_wardrobe only")
    track_bottom = serializers.FloatField(default=20, help_text="sliding_wardrobe only")
    rail_width = serializers.FloatField(default=100, help_text="kitchen_base top rails / kitchen_wall hanging rail")


ENGINE_KEYS = tuple(CabinetFieldsSerializer().fields)


class CabinetInputSerializer(CabinetFieldsSerializer):
    prices = PriceListSerializer(required=False, write_only=True)
    use_catalog_prices = serializers.BooleanField(default=False, write_only=True,
                                                  help_text="fill board prices from the sheet prices of your materials (explicit prices win)")
    save = serializers.BooleanField(default=False, write_only=True)
    name = serializers.CharField(required=False, max_length=160, write_only=True)
    project = serializers.IntegerField(required=False, allow_null=True, write_only=True)


class CalculationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calculation
        fields = ["id", "name", "kind", "project", "inputs", "result", "created_at"]
        read_only_fields = fields
