"""Send reminders for njangi contributions that are coming due soon.

Run on a schedule (e.g. hourly via cron / Celery beat):

    python manage.py send_due_date_reminders --within-hours 24

For every group with a play schedule whose next contribution falls inside the
window, each member who hasn't already paid that occurrence gets an in-app
notification and (if FCM is configured) a push. A member is not reminded twice
for the same occurrence within the window.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from contributions.models import Contribution
from groups.models import NjangiGroup
from notifications.models import Notification
from notifications.services import notify


class Command(BaseCommand):
    help = 'Send push/in-app reminders for upcoming njangi contributions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--within-hours', type=int, default=24,
            help='How many hours ahead to look for due contributions (default 24).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be sent without creating notifications.',
        )

    def handle(self, *args, **options):
        within_hours = options['within_hours']
        dry_run = options['dry_run']

        now = timezone.now()
        cutoff = now + timezone.timedelta(hours=within_hours)
        sent = 0

        groups = NjangiGroup.objects.filter(
            memberships__isnull=False,
        ).distinct().prefetch_related('memberships__user')

        for group in groups:
            due = group.next_play_due_datetime()
            if not due or due < now or due > cutoff:
                continue

            for membership in group.memberships.select_related('user'):
                user = membership.user

                already_paid = Contribution.objects.filter(
                    group=group, user=user, status='completed',
                    due_date=due.date(),
                ).exists()
                if already_paid:
                    continue

                # Don't double-remind for the same occurrence inside the window.
                already_reminded = Notification.objects.filter(
                    user=user, notification_type='payment_reminder',
                    target_type='group', target_id=str(group.id),
                    created_at__gte=now - timezone.timedelta(hours=within_hours),
                ).exists()
                if already_reminded:
                    continue

                when = timezone.localtime(due).strftime('%a %d %b, %H:%M')
                title = f'Contribution due — {group.name}'
                body = (
                    f'Your {group.contribution_amount:,.0f} CFA contribution for '
                    f'{group.name} is due {when}. Pay on time to keep your '
                    f'reliability (MRI) score up.'
                )

                if dry_run:
                    self.stdout.write(f'[dry-run] -> {user.full_name}: {body}')
                else:
                    notify(
                        user, title, body,
                        notification_type='payment_reminder',
                        target_type='group', target_id=str(group.id),
                    )
                sent += 1

        label = 'Would send' if dry_run else 'Sent'
        self.stdout.write(self.style.SUCCESS(f'{label} {sent} reminder(s).'))
