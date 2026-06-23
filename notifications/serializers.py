from rest_framework import serializers

from notifications.models import DeviceToken, Notification


class NotificationSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='notification_type')

    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'type', 'created_at', 'is_read', 'target_type', 'target_id', 'target_view']


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(
        choices=[c[0] for c in DeviceToken.PLATFORM_CHOICES], default='android',
    )
