from rest_framework import serializers

class BotCalcSerializer(serializers.Serializer):
    """Cabinet parameters sent by the bot. Same validation rules as the web calculator."""

    telegram_id = serializers.IntegerField()
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

    def calc_data(self) -> dict:
        data = dict(self.validated_data)
        data.pop("telegram_id", None)
        return data


class BotCuttingListSerializer(BotCalcSerializer):
    name = serializers.CharField(required=False, max_length=160, allow_blank=True)
    project_id = serializers.IntegerField(required=False, allow_null=True)
    sheet_length = serializers.IntegerField(required=False, default=2800, min_value=300, max_value=6000)
    sheet_width = serializers.IntegerField(required=False, default=2070, min_value=300, max_value=6000)

    def calc_data(self) -> dict:
        data = super().calc_data()
        for k in ("name", "project_id", "sheet_length", "sheet_width"):
            data.pop(k, None)
        return data


class BotProjectCreateSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    name = serializers.CharField(max_length=160)
    category = serializers.ChoiceField(choices=["cabinet", "kitchen", "wardrobe", "tv_unit", "bedroom", "office", "living", "other"],
                                       default="cabinet")


class BotProjectRenameSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    name = serializers.CharField(max_length=160)


class BotFileUploadSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    file = serializers.FileField()
    project_id = serializers.IntegerField(required=False, allow_null=True)

