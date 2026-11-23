from rest_framework import serializers

from .models import RoomFlow

ANSWERABLE = ["goal", "photo", "elements", "size", "openings", "style", "furnish"]


class RoomFlowSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomFlow
        fields = ["id", "status", "step", "design", "photo", "created_at", "updated_at"]
        read_only_fields = fields


class AnswerSerializer(serializers.Serializer):
    step = serializers.ChoiceField(choices=ANSWERABLE)
    value = serializers.JSONField()


class ItemSerializer(serializers.Serializer):
    """Shape check only. Sizes, structure and position are validated by the geometry engine, with its own messages."""

    template = serializers.CharField(max_length=64, required=False, allow_blank=True)
    name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    x = serializers.FloatField(required=False)
    z = serializers.FloatField(required=False)
    rot = serializers.IntegerField(required=False)
    width = serializers.FloatField(required=False)
    depth = serializers.FloatField(required=False)
    height = serializers.FloatField(required=False)
    shelves = serializers.IntegerField(required=False)
    doors = serializers.IntegerField(required=False)
    drawers = serializers.IntegerField(required=False)
    thickness = serializers.FloatField(required=False)
    color = serializers.CharField(max_length=7, required=False, allow_blank=True)
    rev = serializers.IntegerField(required=False, min_value=0, help_text="Room revision the client last saw (or send it as an If-Match header).")


class ItemRevSerializer(serializers.Serializer):
    rev = serializers.IntegerField(required=False, min_value=0)


def parse_rev(request, body_rev) -> int:
    """The revision comes from the body (or query for DELETE) or from an If-Match header."""
    rev = body_rev
    if rev is None:
        header = request.META.get("HTTP_IF_MATCH", "").strip().strip('"')
        rev = int(header) if header.isdigit() else None
    if rev is None:
        raise serializers.ValidationError({"rev": "Required: send the room revision in the body or as an If-Match header."})
    return rev


# ----- bot side: the same bodies plus the Telegram account the bot acts for -----------------------------------------

class BotStartSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    new = serializers.BooleanField(required=False, default=False, help_text="Abandon the active flow and start a fresh one.")


class BotTelegramSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()


class BotAnswerSerializer(AnswerSerializer):
    telegram_id = serializers.IntegerField()


class BotItemSerializer(ItemSerializer):
    telegram_id = serializers.IntegerField()


class BotPhotoSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    file = serializers.ImageField()
