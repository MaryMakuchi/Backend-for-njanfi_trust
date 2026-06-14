from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import User
from groups.models import GroupMembership, MembershipRequest, NjangiGroup

PASSWORD = 'Test@123'


class Command(BaseCommand):
    help = (
        'Seed 2 test users for the Patty Crab group: one already a member, '
        'one with a pending membership request.'
    )

    def handle(self, *args, **options):
        grace, _ = User.objects.update_or_create(
            email='grace.member@njangi.test',
            defaults={
                'phone': '+237675555555',
                'full_name': 'Grace Tabe',
                'badge': 'Group President',
                'is_kyc_verified': True,
                'phone_verified': True,
                'email_verified': True,
                'mri_score': Decimal('8.5'),
                'mri_trend': Decimal('0.2'),
                'mri_payment_punctuality': Decimal('8.6'),
                'mri_attendance': Decimal('8.4'),
                'mri_loan_repayment': Decimal('8.5'),
                'mri_contribution_consistency': Decimal('8.5'),
                'mri_community_participation': Decimal('8.5'),
                'wallet_balance': Decimal('60000'),
                'savings_balance': Decimal('0'),
                'social_fund_balance': Decimal('0'),
            },
        )
        grace.set_password(PASSWORD)
        grace.save()

        kevin, _ = User.objects.update_or_create(
            email='kevin.requester@njangi.test',
            defaults={
                'phone': '+237676666666',
                'full_name': 'Kevin Njoya',
                'badge': '',
                'is_kyc_verified': False,
                'phone_verified': True,
                'email_verified': True,
                'mri_score': Decimal('5.0'),
                'mri_trend': Decimal('0.0'),
                'mri_payment_punctuality': Decimal('5.0'),
                'mri_attendance': Decimal('5.0'),
                'mri_loan_repayment': Decimal('0.0'),
                'mri_contribution_consistency': Decimal('5.0'),
                'mri_community_participation': Decimal('5.0'),
                'wallet_balance': Decimal('40000'),
                'savings_balance': Decimal('0'),
                'social_fund_balance': Decimal('0'),
            },
        )
        kevin.set_password(PASSWORD)
        kevin.save()

        group, _ = NjangiGroup.objects.get_or_create(
            name='Patty Crab',
            defaults={
                'contribution_amount': Decimal('25000'),
                'frequency': 'Monthly',
                'max_members': 6,
                'start_date': date(2026, 1, 1),
                'rules': 'Monthly contributions of 25,000 CFA.',
                'target_amount': Decimal('100000'),
                'duration_months': 6,
                'picking_mode': 'random',
                'schedule_generated': False,
                'created_by': grace,
            },
        )

        GroupMembership.objects.update_or_create(
            group=group, user=grace,
            defaults={'role': 'president', 'rotation_position': 1},
        )

        MembershipRequest.objects.get_or_create(
            group=group, user=kevin,
            defaults={'status': 'pending'},
        )

        self.stdout.write(self.style.SUCCESS('Patty Crab test users seeded:'))
        self.stdout.write(f'  grace.member@njangi.test / {PASSWORD}  (President, member of Patty Crab)')
        self.stdout.write(f'  kevin.requester@njangi.test / {PASSWORD}  (Pending join request to Patty Crab)')
