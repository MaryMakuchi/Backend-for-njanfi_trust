"""Firebase Cloud Messaging (FCM) push sender — HTTP v1 API.

Sending is intentionally best-effort and *optional*: if no Firebase
service-account credentials are configured the helpers become no-ops, so the
rest of the app (and the test suite) runs unchanged without a Firebase project.

To enable real pushes, set ``FIREBASE_CREDENTIALS`` (in the environment / .env)
to the path of your Firebase service-account JSON file. This uses the modern
FCM HTTP v1 API via the ``firebase-admin`` SDK.
"""
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# Lazily-initialised firebase_admin app + messaging module. We cache them so the
# SDK is only initialised once per process, on first use.
_fb_app = None
_messaging = None
_init_failed = False


def _credentials_path():
    return getattr(settings, 'FIREBASE_CREDENTIALS', '') or ''


def _ensure_initialised():
    """Initialise firebase_admin once. Returns the messaging module or None."""
    global _fb_app, _messaging, _init_failed
    if _messaging is not None:
        return _messaging
    if _init_failed:
        return None

    path = _credentials_path()
    if not path or not os.path.exists(path):
        _init_failed = True
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        # Reuse an already-initialised default app if present.
        try:
            _fb_app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(path)
            _fb_app = firebase_admin.initialize_app(cred)
        _messaging = messaging
        return _messaging
    except Exception as exc:  # missing package / bad credentials / etc.
        logger.warning('Firebase init failed: %s', exc)
        _init_failed = True
        return None


def push_enabled():
    return _ensure_initialised() is not None


def send_push(tokens, title, body, data=None):
    """Send a push to the given device tokens. Returns the number delivered.

    No-ops (returns 0) when push isn't configured or there are no tokens.
    Never raises — push failures must not break the request that triggered them.
    """
    tokens = [t for t in (tokens or []) if t]
    if not tokens:
        return 0

    messaging = _ensure_initialised()
    if messaging is None:
        return 0

    # FCM v1 data payload values must all be strings.
    str_data = {k: str(v) for k, v in (data or {}).items()}

    try:
        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            data=str_data,
            android=messaging.AndroidConfig(priority='high'),
        )
        response = messaging.send_each_for_multicast(message)
        return int(response.success_count)
    except Exception as exc:  # network/SDK errors — never propagate
        logger.warning('FCM push error: %s', exc)
        return 0


def send_push_to_user(user, title, body, data=None):
    """Push to all of a user's registered devices."""
    tokens = list(user.device_tokens.values_list('token', flat=True))
    return send_push(tokens, title, body, data)
