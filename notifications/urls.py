from django.urls import path

from notifications.views import MarkNotificationReadView, NotificationListView

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<uuid:pk>/read/', MarkNotificationReadView.as_view(), name='notification-read'),
]
