from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


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


class MarkNotificationReadView(APIView):
    def patch(self, request, pk):
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if not notification:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)
