"""Helpers for creating notifications that are both in-app and pushed.

Use :func:`notify` instead of ``Notification.objects.create`` when you also
want the message delivered as a push to the member's devices. Push is
best-effort and optional (see ``notifications.fcm``).
"""
from notifications.fcm import send_push_to_user
from notifications.models import Notification


def notify(user, title, body, notification_type, *,
           target_type='', target_id='', target_view='', push=True):
    """Create an in-app notification and (optionally) push it to the user."""
    notification = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        notification_type=notification_type,
        target_type=target_type,
        target_id=target_id,
        target_view=target_view,
    )
    if push:
        send_push_to_user(
            user, title, body,
            data={
                'notification_id': str(notification.id),
                'target_type': target_type,
                'target_id': target_id,
                'target_view': target_view,
            },
        )
    return notification
