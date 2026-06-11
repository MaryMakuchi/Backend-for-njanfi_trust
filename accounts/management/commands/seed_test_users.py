from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import LinkedAccount, User
from contributions.models import Contribution
from groups.models import GroupMembership, NjangiGroup, SocialFund, SocialFundContribution
from ledger.models import Transaction
from loans.models import Loan
from notifications.models import Notification

PASSWORD = 'Test@1234'


class Command(BaseCommand):
    help = 'Seed 4 test users with different roles, a shared group, and sample interactions'

    def handle(self, *args, **options):
        # --- Users -------------------------------------------------------
        aisha, _ = User.objects.update_or_create(
            email='aisha.president@njangi.test',
            defaults={
                'phone': '+237670000011',
                'full_name': 'Aisha Mballa',
                'badge': 'Group President',
                'is_kyc_verified': True,
                'phone_verified': True,
                'email_verified': True,
                'mri_score': Decimal('9.6'),
                'mri_trend': Decimal('0.8'),
                'mri_payment_punctuality': Decimal('9.8'),
                'mri_attendance': Decimal('9.7'),
                'mri_loan_repayment': Decimal('9.5'),
                'mri_contribution_consistency': Decimal('9.6'),
                'mri_community_participation': Decimal('9.4'),
                'wallet_balance': Decimal('120000'),
                'savings_balance': Decimal('850000'),
                'social_fund_balance': Decimal('60000'),
            },
        )
        aisha.set_password(PASSWORD)
        aisha.save()

        brian, _ = User.objects.update_or_create(
            email='brian.treasurer@njangi.test',
            defaults={
                'phone': '+237670000012',
                'full_name': 'Brian Tabi',
                'badge': 'Treasurer',
                'is_kyc_verified': True,
                'phone_verified': True,
                'email_verified': True,
                'mri_score': Decimal('8.9'),
                'mri_trend': Decimal('0.3'),
                'mri_payment_punctuality': Decimal('9.0'),
                'mri_attendance': Decimal('8.8'),
                'mri_loan_repayment': Decimal('9.0'),
                'mri_contribution_consistency': Decimal('8.7'),
                'mri_community_participation': Decimal('8.9'),
                'wallet_balance': Decimal('75000'),
                'savings_balance': Decimal('430000'),
                'social_fund_balance': Decimal('40000'),
            },
        )
        brian.set_password(PASSWORD)
        brian.save()

        carine, _ = User.objects.update_or_create(
            email='carine.member@njangi.test',
            defaults={
                'phone': '+237670000013',
                'full_name': 'Carine Fonki',
                'badge': 'Active Member',
                'is_kyc_verified': True,
                'phone_verified': True,
                'email_verified': True,
                'mri_score': Decimal('7.8'),
                'mri_trend': Decimal('-0.4'),
                'mri_payment_punctuality': Decimal('7.5'),
                'mri_attendance': Decimal('8.0'),
                'mri_loan_repayment': Decimal('7.2'),
                'mri_contribution_consistency': Decimal('7.9'),
                'mri_community_participation': Decimal('8.1'),
                'wallet_balance': Decimal('230000'),
                'savings_balance': Decimal('150000'),
                'social_fund_balance': Decimal('15000'),
            },
        )
        carine.set_password(PASSWORD)
        carine.save()

        david, _ = User.objects.update_or_create(
            email='david.newuser@njangi.test',
            defaults={
                'phone': '+237670000014',
                'full_name': 'David Eyong',
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
                'wallet_balance': Decimal('25000'),
                'savings_balance': Decimal('0'),
                'social_fund_balance': Decimal('0'),
            },
        )
        david.set_password(PASSWORD)
        david.save()

        # --- Shared group --------------------------------------------------
        group, _ = NjangiGroup.objects.get_or_create(
            invitation_code='QATEST1',
            defaults={
                'name': 'QA TEST GROUP',
                'contribution_amount': Decimal('50000'),
                'frequency': 'Monthly',
                'max_members': 4,
                'start_date': date(2026, 1, 1),
                'rules': 'Monthly contributions of 50,000 CFA. Used for QA testing.',
                'fund_balance': Decimal('150000'),
                'cycle_progress': 1,
                'target_amount': Decimal('200000'),
                'duration_months': 4,
                'picking_mode': 'random',
                'schedule_generated': False,
                'created_by': aisha,
            },
        )

        GroupMembership.objects.update_or_create(
            group=group, user=aisha,
            defaults={'role': 'president', 'rotation_position': 1},
        )
        GroupMembership.objects.update_or_create(
            group=group, user=brian,
            defaults={'role': 'treasurer', 'rotation_position': 2},
        )
        GroupMembership.objects.update_or_create(
            group=group, user=carine,
            defaults={'role': 'member', 'rotation_position': 3},
        )
        GroupMembership.objects.update_or_create(
            group=group, user=david,
            defaults={'role': 'member', 'rotation_position': 4},
        )

        # --- Contributions ---------------------------------------------------
        Contribution.objects.update_or_create(
            group=group, user=aisha, due_date=date(2026, 5, 1),
            defaults={
                'amount': Decimal('50000'), 'status': 'completed',
                'paid_date': timezone.now() - timedelta(days=40),
                'payment_method': 'MTN MoMo',
            },
        )
        Contribution.objects.update_or_create(
            group=group, user=brian, due_date=date(2026, 5, 1),
            defaults={
                'amount': Decimal('50000'), 'status': 'completed',
                'paid_date': timezone.now() - timedelta(days=38),
                'payment_method': 'Orange Money',
            },
        )
        Contribution.objects.update_or_create(
            group=group, user=carine, due_date=date(2026, 6, 1),
            defaults={'amount': Decimal('50000'), 'status': 'late'},
        )
        Contribution.objects.update_or_create(
            group=group, user=david, due_date=date(2026, 6, 15),
            defaults={'amount': Decimal('50000'), 'status': 'outstanding'},
        )

        # --- Social fund ------------------------------------------------------
        fund, _ = SocialFund.objects.get_or_create(
            group=group, reason='Emergency Relief Fund',
            defaults={
                'target_amount': Decimal('100000'),
                'balance': Decimal('35000'),
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 12, 31),
                'created_by': aisha,
                'is_active': True,
            },
        )
        SocialFundContribution.objects.get_or_create(
            social_fund=fund, user=aisha, amount=Decimal('20000'),
        )
        SocialFundContribution.objects.get_or_create(
            social_fund=fund, user=brian, amount=Decimal('15000'),
        )

        # --- Loans --------------------------------------------------------
        Loan.objects.update_or_create(
            user=carine, group=group, purpose='Medical expenses',
            defaults={
                'amount': Decimal('150000'), 'duration_months': 6,
                'status': 'active', 'interest_rate': Decimal('5.0'),
                'remaining_balance': Decimal('100000'),
                'due_date': date(2026, 11, 1),
                'approved_date': date(2026, 5, 1),
            },
        )
        Loan.objects.update_or_create(
            user=david, group=group, purpose='Small business stock',
            defaults={
                'amount': Decimal('75000'), 'duration_months': 4,
                'status': 'pending', 'interest_rate': Decimal('5.0'),
                'remaining_balance': Decimal('0'),
            },
        )

        # --- Linked accounts -----------------------------------------------
        LinkedAccount.objects.get_or_create(
            user=aisha, account_type='mobile_money', provider='MTN MoMo',
            account_number='670000011',
            defaults={'account_name': 'Aisha Mballa', 'is_default': True},
        )
        LinkedAccount.objects.get_or_create(
            user=brian, account_type='mobile_money', provider='Orange Money',
            account_number='690000012',
            defaults={'account_name': 'Brian Tabi', 'is_default': True},
        )
        LinkedAccount.objects.get_or_create(
            user=brian, account_type='bank', provider='Afriland First Bank',
            account_number='4001234567',
            defaults={'account_name': 'Brian Tabi', 'is_default': False},
        )
        LinkedAccount.objects.get_or_create(
            user=carine, account_type='mobile_money', provider='MTN MoMo',
            account_number='670000013',
            defaults={'account_name': 'Carine Fonki', 'is_default': True},
        )
        LinkedAccount.objects.get_or_create(
            user=david, account_type='mobile_money', provider='Orange Money',
            account_number='690000014',
            defaults={'account_name': 'David Eyong', 'is_default': True},
        )

        # --- Transactions -----------------------------------------------------
        def seed_transactions(user, items):
            if Transaction.objects.filter(user=user).exists():
                return
            Transaction.objects.bulk_create([
                Transaction(user=user, **item) for item in items
            ])

        seed_transactions(aisha, [
            dict(group=group, title='Contribution - QA TEST GROUP', amount=Decimal('50000'),
                 transaction_type='contribution', status='verified', is_credit=False,
                 hash='0xaa01'),
            dict(title='Wallet Top Up', amount=Decimal('100000'),
                 transaction_type='wallet_topup', status='completed', is_credit=True),
            dict(title='Savings Deposit', amount=Decimal('200000'),
                 transaction_type='savings_deposit', status='completed', is_credit=False),
            dict(group=group, title='Social Fund Contribution', amount=Decimal('20000'),
                 transaction_type='social_fund', status='completed', is_credit=False),
        ])

        seed_transactions(brian, [
            dict(group=group, title='Contribution - QA TEST GROUP', amount=Decimal('50000'),
                 transaction_type='contribution', status='verified', is_credit=False,
                 hash='0xaa02'),
            dict(title='Wallet Top Up', amount=Decimal('75000'),
                 transaction_type='wallet_topup', status='completed', is_credit=True),
            dict(title='Savings Deposit', amount=Decimal('100000'),
                 transaction_type='savings_deposit', status='completed', is_credit=False),
            dict(group=group, title='Social Fund Contribution', amount=Decimal('15000'),
                 transaction_type='social_fund', status='completed', is_credit=False),
        ])

        seed_transactions(carine, [
            dict(group=group, title='Loan Disbursement - QA TEST GROUP', amount=Decimal('150000'),
                 transaction_type='loan_disbursement', status='completed', is_credit=True),
            dict(group=group, title='Loan Repayment - QA TEST GROUP', amount=Decimal('50000'),
                 transaction_type='loan_repayment', status='completed', is_credit=False),
            dict(title='Wallet Top Up', amount=Decimal('50000'),
                 transaction_type='wallet_topup', status='completed', is_credit=True),
            dict(title='Savings Deposit', amount=Decimal('150000'),
                 transaction_type='savings_deposit', status='completed', is_credit=False),
        ])

        seed_transactions(david, [
            dict(title='Wallet Top Up', amount=Decimal('25000'),
                 transaction_type='wallet_topup', status='completed', is_credit=True),
            dict(group=group, title='Contribution - QA TEST GROUP', amount=Decimal('50000'),
                 transaction_type='contribution', status='pending', is_credit=False,
                 hash='0xaa04'),
        ])

        # --- Notifications ------------------------------------------------------
        def seed_notifications(user, items):
            if Notification.objects.filter(user=user).exists():
                return
            Notification.objects.bulk_create([
                Notification(user=user, **item) for item in items
            ])

        seed_notifications(aisha, [
            dict(title='Group Announcement', body='QA TEST GROUP is now full. Assign the picking order from the group page.',
                 notification_type='group_announcement'),
            dict(title='Contribution Confirmed', body='Your contribution of 50,000 CFA was received.',
                 notification_type='contribution_confirmation'),
        ])

        seed_notifications(brian, [
            dict(title='Upcoming Payout', body='The next payout for QA TEST GROUP is scheduled soon.',
                 notification_type='upcoming_payout'),
            dict(title='Contribution Confirmed', body='Your contribution of 50,000 CFA was received.',
                 notification_type='contribution_confirmation'),
        ])

        seed_notifications(carine, [
            dict(title='Loan Approved', body='Your loan request of 150,000 CFA has been approved and disbursed to your wallet.',
                 notification_type='loan_approval'),
            dict(title='Payment Reminder', body='Your contribution to QA TEST GROUP is overdue.',
                 notification_type='payment_reminder'),
        ])

        seed_notifications(david, [
            dict(title='Welcome to QA TEST GROUP', body='You have joined QA TEST GROUP. Complete your KYC to unlock loans.',
                 notification_type='group_announcement'),
            dict(title='Payment Reminder', body='Your first contribution of 50,000 CFA is due soon.',
                 notification_type='payment_reminder'),
        ])

        self.stdout.write(self.style.SUCCESS('Test users seeded successfully:'))
        for email, role in [
            ('aisha.president@njangi.test', 'President / Group creator'),
            ('brian.treasurer@njangi.test', 'Treasurer'),
            ('carine.member@njangi.test', 'Member with active loan'),
            ('david.newuser@njangi.test', 'New member, KYC pending, pending loan'),
        ]:
            self.stdout.write(f'  {email} / {PASSWORD}  ({role})')
