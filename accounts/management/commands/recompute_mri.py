from django.core.management.base import BaseCommand

from accounts.models import User
from accounts.mri import recompute_mri


class Command(BaseCommand):
    help = (
        'Recompute every member\'s MRI score from their actual contribution and '
        'loan history. Fair and recoverable: overdue items lower the score, and '
        'paying them off raises it again. Replaces the old flat-rate demerits.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet', action='store_true',
            help='Do not record audit events / notifications, just recompute scores.',
        )

    def handle(self, *args, **options):
        record_event = not options['quiet']
        count = 0
        for user in User.objects.all():
            recompute_mri(user, record_event=record_event)
            count += 1
        self.stdout.write(self.style.SUCCESS(
            f'Recomputed MRI for {count} member(s).'
        ))
