import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Create or update a superuser from DJANGO_SUPERUSER_* environment '
        'variables. Idempotent and safe to run on every deploy; does nothing '
        'when the email/password variables are not set.'
    )

    def handle(self, *args, **options):
        User = get_user_model()

        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        phone = os.environ.get('DJANGO_SUPERUSER_PHONE', '')
        full_name = os.environ.get('DJANGO_SUPERUSER_FULL_NAME', 'Administrator')

        if not email or not password:
            self.stdout.write(
                'DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD not set; '
                'skipping superuser creation.'
            )
            return

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'phone': phone, 'full_name': full_name},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if phone:
            user.phone = phone
        if full_name:
            user.full_name = full_name
        user.set_password(password)
        user.save()

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} superuser: {email}'))
