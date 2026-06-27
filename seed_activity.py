"""Drive demo activity for "Nfah Njangi 2026":

  1. Approve the pending membership request (yours) so the group is full.
  2. Make every member play their njangi (a contribution recorded on-chain),
     so the Blockchain Ledger shows real verified entries.
  3. Start a savings period and have several members save, so the treasurer's
     oversight of group savings is clearly demonstrable.

Run on your local machine AFTER you have registered an account and tapped
"Request to join" with the invite code:

    python manage.py shell < seed_activity.py

Idempotent-ish: safe to re-run; it will add more contributions/savings each
time but will not duplicate the membership.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.services import record_transaction
from contributions.models import Contribution
from groups.models import (
    GroupMembership,
    MembershipRequest,
    NjangiGroup,
    SavingsContribution,
    SavingsPeriod,
)
from notifications.models import Notification

GROUP_NAME = 'Nfah Njangi 2026'
CONTRIBUTION = Decimal('5000')

group = NjangiGroup.objects.filter(name=GROUP_NAME).order_by('created_at').first()
if not group:
    raise SystemExit(f'Group "{GROUP_NAME}" not found. Run seed_demo.py first.')

president = GroupMembership.objects.filter(group=group, role='president').first()

# ---------------------------------------------------------------------------
# 1. Approve the pending membership request (mirrors RespondMembershipRequestView)
# ---------------------------------------------------------------------------
pending = MembershipRequest.objects.filter(group=group, status='pending').select_related('user')
if not pending.exists():
    print('No pending membership requests to approve.')
for req in pending:
    if group.member_count >= group.max_members:
        print(f'Group full ({group.max_members}); cannot accept {req.user.full_name}.')
        break
    already = GroupMembership.objects.filter(group=group, user=req.user).exists()
    if not already:
        position = group.member_count + 1
        GroupMembership.objects.create(
            group=group,
            user=req.user,
            role='member',
            rotation_position=position,
            slot_name=req.user.full_name,
        )
        print(f'Approved {req.user.full_name} as member #{position}.')
    req.status = 'accepted'
    req.decided_at = timezone.now()
    req.save(update_fields=['status', 'decided_at'])
    Notification.objects.create(
        user=req.user,
        title=f'Welcome to {group.name}!',
        body=f'Your request to join {group.name} has been accepted. You are now a member.',
        notification_type='group_announcement',
        target_type='group',
        target_id=str(group.id),
    )

# ---------------------------------------------------------------------------
# 2. Every member plays their njangi -> on-chain ledger entries
# ---------------------------------------------------------------------------
print('\nPlaying njangi for every member...')
memberships = GroupMembership.objects.filter(group=group).select_related('user')
for m in memberships:
    user = m.user
    Contribution.objects.create(
        group=group,
        user=user,
        amount=CONTRIBUTION,
        due_date=timezone.now().date(),
        status='completed',
        paid_date=timezone.now(),
        payment_method='mobile_money',
    )
    group.fund_balance += CONTRIBUTION
    group.cycle_progress = min(group.cycle_progress + 1, group.max_members)
    tx = record_transaction(
        user,
        title=f'Contribution - {group.name}',
        amount=CONTRIBUTION,
        transaction_type='contribution',
        is_credit=False,
        group=group,
    )
    try:
        from accounts.mri import recompute_mri
        recompute_mri(user)
    except Exception as exc:  # MRI recompute is non-critical for the demo
        print(f'  (MRI recompute skipped for {user.full_name}: {exc})')
    print(f'  {user.full_name:18} contributed {CONTRIBUTION} CFA  ->  {tx.status} {tx.hash[:18]}...')
group.save(update_fields=['fund_balance', 'cycle_progress'])

# ---------------------------------------------------------------------------
# 3. Start a savings period and have several members save (treasurer oversight)
# ---------------------------------------------------------------------------
print('\nStarting savings period and recording deposits...')
period = SavingsPeriod.objects.filter(group=group, status='active').order_by('-created_at').first()
if not period:
    period = SavingsPeriod.objects.create(
        group=group,
        started_by=president.user if president else None,
        interest_rate=Decimal('5.00'),
        interest_type='simple',
        start_date=date(2026, 6, 28),
        end_date=date(2027, 1, 3),
        status='active',
    )
    print(f'  Created savings period {period.start_date} -> {period.end_date} @ {period.interest_rate}% simple')
else:
    print('  Using existing active savings period.')

# A few members save different amounts (recorded on-chain, source = MoMo so no
# wallet balance is required).
SAVERS = [
    ('thelma.balike@demo.com',   Decimal('20000')),
    ('theresia.ngonda@demo.com', Decimal('15000')),
    ('ndeh.mark@demo.com',       Decimal('10000')),
    ('juliana.makuchi@demo.com', Decimal('12000')),
]
for email, amount in SAVERS:
    sm = memberships.filter(user__email=email).first()
    if not sm:
        print(f'  (skipped {email}: not a member)')
        continue
    SavingsContribution.objects.create(period=period, user=sm.user, amount=amount)
    tx = record_transaction(
        sm.user,
        title=f'Savings deposit (MTN MoMo) - {group.name}',
        amount=amount,
        transaction_type='savings_deposit',
        is_credit=False,
        group=group,
    )
    print(f'  {sm.user.full_name:18} saved {amount} CFA  ->  {tx.status} {tx.hash[:18]}...')

total_saved = sum(c.amount for c in SavingsContribution.objects.filter(period=period))
print(f'\nGroup fund balance: {group.fund_balance} CFA')
print(f'Total group savings this period: {total_saved} CFA')
print(f'Treasurer overseeing savings: '
      f'{GroupMembership.objects.filter(group=group, role="treasurer").first().user.full_name}')
print('\nDone. Open the Blockchain Ledger screen to see the verified entries.')
