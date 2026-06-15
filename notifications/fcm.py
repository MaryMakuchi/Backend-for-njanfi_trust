"""Firebase Cloud Messaging (FCM) push sender.

Sending is intentionally best-effort and *optional*: if no ``FCM_SERVER_KEY``
is configured the helpers become no-ops, so the rest of the app (and the test
suite) runs unchanged without a Firebase project. Configure the key via the
``FCM_SERVER_KEY`` environment variable to enable real pushes.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

FCM_ENDPOINT = 'https://fcm.googleapis.com/fcm/send'


def _server_key():
    return getattr(settings, 'FCM_SERVER_KEY', '') or ''


def push_enabled():
    return bool(_server_key())


def send_push(tokens, title, body, data=None):
    """Send a push to the given device tokens. Returns the number delivered.

    No-ops (returns 0) when push isn't configured or there are no tokens.
    Never raises — push failures must not break the request that triggered them.
    """
    tokens = [t for t in (tokens or []) if t]
    if not tokens or not push_enabled():
        return 0

    import requests

    headers = {
        'Authorization': f'key={_server_key()}',
        'Content-Type': 'application/json',
    }
    payload = {
        'registration_ids': tokens,
        'notification': {'title': title, 'body': body},
        'data': {k: str(v) for k, v in (data or {}).items()},
        'priority': 'high',
    }

    try:
        resp = requests.post(FCM_ENDPOINT, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning('FCM push failed (%s): %s', resp.status_code, resp.text[:200])
            return 0
        result = resp.json()
        return int(result.get('success', 0))
    except Exception as exc:  # network/JSON/etc. — never propagate
        logger.warning('FCM push error: %s', exc)
        return 0


def send_push_to_user(user, title, body, data=None):
    """Push to all of a user's registered devices."""
    tokens = list(user.device_tokens.values_list('token', flat=True))
    return send_push(tokens, title, body, data)
