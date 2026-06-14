from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import User
from groups.models import GroupMembership, MembershipRequest, NjangiGroup

PASSWORD = 'Test@123'
GROUP_NAME = 'Patty Crab'


class Command(BaseCommand):
    help = (
        'Seed 2 test logins for the existing "Patty Crab" group: one as a '
        'member, one with a pending membership request. Does NOT create the '
        'group itself — it attaches to a Patty Crab group you already created.'
    )

    def handle(self, *args, **options):
        grace, _ = User.objects.update_or_create(
            email='grace.member@njangi.test',
            defaults={
                'phone': '+237675555555',
                'full_name': 'Grace Tabe',
                'badge': 'Active Member',
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

        self.stdout.write(self.style.SUCCESS('Test logins ready:'))
        self.stdout.write(f'  grace.member@njangi.test / {PASSWORD}')
        self.stdout.write(f'  kevin.requester@njangi.test / {PASSWORD}')

        # Attach to an EXISTING Patty Crab group if you have one. We never
        # create the group here, so it won't clash with your own.
        group = NjangiGroup.objects.filter(name=GROUP_NAME).order_by('created_at').first()
        if not group:
            self.stdout.write(self.style.WARNING(
                f'No "{GROUP_NAME}" group found yet. Create it in the app, then '
                f're-run this command to attach Grace (member) and Kevin (pending request).'
            ))
            return

        GroupMembership.objects.update_or_create(
            group=group, user=grace,
            defaults={'role': 'member'},
        )
        MembershipRequest.objects.get_or_create(
            group=group, user=kevin,
            defaults={'status': 'pending'},
        )
        self.stdout.write(self.style.SUCCESS(
            f'Grace added as a member of "{group.name}", '
            f'Kevin added as a pending join request.'
        ))
