from django.urls import path

from notifications.views import (
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    NotificationListView,
    RegisterDeviceTokenView,
    UnregisterDeviceTokenView,
    UnreadCountView,
)

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/read-all/', MarkAllNotificationsReadView.as_view(), name='notification-read-all'),
    path('notifications/devices/register/', RegisterDeviceTokenView.as_view(), name='device-register'),
    path('notifications/devices/unregister/', UnregisterDeviceTokenView.as_view(), name='device-unregister'),
    path('notifications/<uuid:pk>/read/', MarkNotificationReadView.as_view(), name='notification-read'),
]
