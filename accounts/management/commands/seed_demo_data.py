from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from contributions.models import Contribution
from groups.models import GroupMembership, NjangiGroup
from ledger.models import Transaction
from loans.models import Loan
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Seed demo data matching the Flutter mock dataset'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            email='makuchi@example.com',
            defaults={
                'phone': '+237600000001',
                'full_name': 'Makuchi',
                'badge': 'Trusted Member',
                'is_kyc_verified': True,
                'phone_verified': True,
                'email_verified': True,
                'mri_score': Decimal('9.4'),
                'mri_trend': Decimal('1.2'),
                'mri_payment_punctuality': Decimal('9.8'),
                'mri_attendance': Decimal('9.2'),
                'mri_loan_repayment': Decimal('9.5'),
                'mri_contribution_consistency': Decimal('9.6'),
                'mri_community_participation': Decimal('8.9'),
                'wallet_balance': Decimal('500000'),
                'social_fund_balance': Decimal('180000'),
            },
        )
        if created:
            user.set_password('password123')
            user.save()
            self.stdout.write(self.style.SUCCESS('Created demo user makuchi@example.com / password123'))
        else:
            self.stdout.write('Demo user already exists')

        group_a, _ = NjangiGroup.objects.get_or_create(
            invitation_code='NJA2025',
            defaults={
                'name': 'NJANGI HOUSE A',
                'contribution_amount': Decimal('50000'),
                'frequency': 'Monthly',
                'max_members': 20,
                'start_date': date(2025, 1, 1),
                'rules': 'Monthly contributions, rotation by join order.',
                'fund_balance': Decimal('1000000'),
                'cycle_progress': 8,
                'created_by': user,
            },
        )
        GroupMembership.objects.get_or_create(
            group=group_a, user=user,
            defaults={'role': 'president', 'rotation_position': 1},
        )

        group_b, _ = NjangiGroup.objects.get_or_create(
            invitation_code='FAM2025',
            defaults={
                'name': 'FAMILY SAVERS',
                'contribution_amount': Decimal('25000'),
                'frequency': 'Bi-weekly',
                'max_members': 15,
                'start_date': date(2025, 6, 1),
                'fund_balance': Decimal('300000'),
                'cycle_progress': 5,
                'created_by': user,
            },
        )
        GroupMembership.objects.get_or_create(
            group=group_b, user=user,
            defaults={'role': 'president', 'rotation_position': 1},
        )

        NjangiGroup.objects.get_or_create(
            invitation_code='YTH2026',
            defaults={
                'name': 'YOUTH INVESTORS',
                'contribution_amount': Decimal('100000'),
                'frequency': 'Monthly',
                'max_members': 10,
                'start_date': date(2026, 1, 1),
                'fund_balance': Decimal('800000'),
                'cycle_progress': 3,
                'created_by': user,
            },
        )

        Contribution.objects.get_or_create(
            group=group_a, user=user, due_date=date(2026, 6, 1),
            defaults={
                'amount': Decimal('50000'), 'status': 'completed',
                'paid_date': timezone.now(), 'payment_method': 'MTN MoMo',
            },
        )
        Contribution.objects.get_or_create(
            group=group_b, user=user, due_date=date(2026, 6, 15),
            defaults={'amount': Decimal('25000'), 'status': 'outstanding'},
        )

        Loan.objects.get_or_create(
            user=user, purpose='Business expansion',
            defaults={
                'amount': Decimal('350000'), 'duration_months': 6,
                'status': 'active', 'interest_rate': Decimal('5.0'),
                'remaining_balance': Decimal('175000'),
                'due_date': date(2026, 9, 1), 'group': group_a,
                'approved_date': date(2026, 3, 1),
            },
        )

        if not Transaction.objects.filter(user=user).exists():
            Transaction.objects.bulk_create([
                Transaction(
                    user=user, group=group_a, title='Contribution - NJANGI HOUSE A',
                    amount=Decimal('50000'), transaction_type='contribution',
                    status='verified', hash='0x7a3f8b2c1d9e4f6a8b0c2d4e6f8a0b2c', is_credit=False,
                ),
                Transaction(
                    user=user, title='Loan Repayment', amount=Decimal('58333'),
                    transaction_type='loan_repayment', status='completed', is_credit=False,
                ),
            ])

        if not Notification.objects.filter(user=user).exists():
            Notification.objects.bulk_create([
                Notification(
                    user=user, title='Payment Reminder',
                    body='Your contribution to FAMILY SAVERS is due in 3 days.',
                    notification_type='payment_reminder',
                ),
                Notification(
                    user=user, title='Loan Approved',
                    body='Your loan request of 100,000 CFA has been approved.',
                    notification_type='loan_approval',
                ),
            ])

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
