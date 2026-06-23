from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import DeviceToken, Notification
from notifications.serializers import DeviceTokenSerializer, NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class UnreadCountView(APIView):
    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count})


class MarkAllNotificationsReadView(APIView):
    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user, is_read=False,
        ).update(is_read=True)
        return Response({'marked_read': updated, 'unread_count': 0})


class RegisterDeviceTokenView(APIView):
    """Register (or refresh) this device's push token for the current user."""

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']

        DeviceToken.objects.update_or_create(
            token=token,
            defaults={'user': request.user, 'platform': platform},
        )
        return Response({'detail': 'Device registered for push notifications.'})


class UnregisterDeviceTokenView(APIView):
    """Remove a device token (e.g. on logout) so it stops receiving pushes."""

    def post(self, request):
        token = request.data.get('token')
        if token:
            DeviceToken.objects.filter(token=token, user=request.user).delete()
        return Response({'detail': 'Device unregistered.'})


class MarkNotificationReadView(APIView):
    def patch(self, request, pk):
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if not notification:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)
