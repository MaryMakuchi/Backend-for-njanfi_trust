from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='notification_type')

    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'type', 'created_at', 'is_read', 'target_type', 'target_id', 'target_view']
