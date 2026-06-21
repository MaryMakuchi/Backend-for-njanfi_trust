"""Send a test push notification to a single user, to verify FCM delivery.

Usage:
    python manage.py send_test_push patty@example.com
    python manage.py send_test_push --name Patty
    python manage.py send_test_push patty@example.com --title "Hi" --body "Test"

Looks up the user by email (positional) or a case-insensitive name match
(--name), creates an in-app notification, and attempts a push. Reports how many
devices were reached so you can tell whether the token/credentials are set up.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from notifications.fcm import push_enabled, send_push_to_user
from notifications.services import notify

User = get_user_model()


class Command(BaseCommand):
    help = 'Send a test push notification to one user.'

    def add_arguments(self, parser):
        parser.add_argument('email', nargs='?', help='User email address')
        parser.add_argument('--name', help='Case-insensitive full-name match')
        parser.add_argument('--title', default='Test Notification')
        parser.add_argument(
            '--body',
            default='If you can see this, push notifications are working! 🎉',
        )

    def handle(self, *args, **options):
        email = options.get('email')
        name = options.get('name')

        if email:
            user = User.objects.filter(email__iexact=email).first()
        elif name:
            matches = list(User.objects.filter(full_name__icontains=name))
            if len(matches) > 1:
                names = ', '.join(f'{u.full_name} <{u.email}>' for u in matches)
                raise CommandError(f'Multiple users match "{name}": {names}')
            user = matches[0] if matches else None
        else:
            raise CommandError('Provide an email or --name.')

        if user is None:
            raise CommandError('No matching user found.')

        device_count = user.device_tokens.count()
        self.stdout.write(
            f'User: {user.full_name} <{user.email}> — '
            f'{device_count} registered device(s).'
        )
        if not push_enabled():
            self.stdout.write(self.style.WARNING(
                'FCM is NOT configured (FIREBASE_CREDENTIALS unset or invalid). '
                'An in-app notification will still be created, but no push '
                'will be delivered.'
            ))
        if device_count == 0:
            self.stdout.write(self.style.WARNING(
                'This user has no registered devices. The phone must log in to '
                'the app at least once (with Firebase configured) to register.'
            ))

        # Create the in-app record without pushing, then push separately so we
        # can report how many devices were actually reached.
        notify(
            user,
            options['title'],
            options['body'],
            notification_type='group_announcement',
            push=False,
        )
        delivered = send_push_to_user(user, options['title'], options['body'])

        self.stdout.write(self.style.SUCCESS(
            f'Done — in-app notification created; push delivered to '
            f'{delivered} of {device_count} device(s).'
        ))
        if device_count and not delivered:
            self.stdout.write(self.style.WARNING(
                'Push reached 0 devices despite registered tokens — the token '
                'may be stale (reinstall/relogin on the phone) or credentials '
                'are wrong. Check the server log for an "FCM push error".'
            ))
