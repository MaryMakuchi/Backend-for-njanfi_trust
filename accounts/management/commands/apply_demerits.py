from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import MriEvent
from accounts.services import apply_mri_demerit

# Demerit point values on the 0-10 MRI scale.
MISSED_CONTRIBUTION_POINTS = Decimal('0.5')
LOAN_DEFAULT_POINTS = Decimal('1.0')


class Command(BaseCommand):
    help = (
        'Scan for demerit-worthy conditions (overdue contributions, defaulted '
        'loans) and apply MRI demerits idempotently.'
    )

    def handle(self, *args, **options):
        # Local imports so this command does not import other apps at module load.
        from contributions.models import Contribution
        from loans.models import Loan

        from accounts.models import User

        today = timezone.now().date()
        missed = 0
        defaults = 0

        # Overdue unpaid contributions -> 'missed_contribution', once each.
        # Use .values() (selecting only the columns we need, joining group__name)
        # so we never load the full related rows.
        overdue_contribs = Contribution.objects.filter(
            status__in=['pending', 'outstanding', 'late'],
            due_date__lt=today,
        ).values('id', 'user_id', 'amount', 'due_date', 'group__name')
        for contrib in overdue_contribs:
            ref = f'contribution:{contrib["id"]}'
            if MriEvent.objects.filter(
                reason='missed_contribution', reference_id=ref,
            ).exists():
                continue
            group_name = contrib['group__name'] or 'a group'
            apply_mri_demerit(
                User.objects.get(pk=contrib['user_id']),
                MISSED_CONTRIBUTION_POINTS,
                'missed_contribution',
                f'Missed contribution of {contrib["amount"]} for {group_name} '
                f'(due {contrib["due_date"]}).',
                reference_id=ref,
            )
            missed += 1

        # Active loans past due with remaining balance -> 'loan_default', once
        # per loan per overdue period (keyed on loan id + due_date).
        overdue_loans = Loan.objects.filter(
            status='active',
            due_date__lt=today,
            remaining_balance__gt=0,
        ).values('id', 'user_id', 'amount', 'due_date', 'remaining_balance')
        for loan in overdue_loans:
            ref = f'loan:{loan["id"]}:{loan["due_date"]}'
            if MriEvent.objects.filter(
                reason='loan_default', reference_id=ref,
            ).exists():
                continue
            apply_mri_demerit(
                User.objects.get(pk=loan['user_id']),
                LOAN_DEFAULT_POINTS,
                'loan_default',
                f'Loan of {loan["amount"]} is overdue (due {loan["due_date"]}) '
                f'with {loan["remaining_balance"]} still outstanding.',
                reference_id=ref,
            )
            defaults += 1

        self.stdout.write(self.style.SUCCESS(
            f'Applied {missed} missed_contribution demerit(s) and '
            f'{defaults} loan_default demerit(s).'
        ))
