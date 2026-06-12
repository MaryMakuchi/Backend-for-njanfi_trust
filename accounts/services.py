from decimal import Decimal

from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import MriEvent, User
from accounts.serializers import UserSerializer

# MRI score floor (scores live on a 0-10 Decimal scale).
MRI_FLOOR = Decimal('0')


def apply_mri_demerit(user, points, reason, description, reference_id=''):
    """Decrement a user's stored mri_score, record an MriEvent and notify them.

    ``points`` is the magnitude of the penalty (a positive Decimal/number on the
    0-10 scale). The new score is clamped to ``MRI_FLOOR``. Returns the new score.
    """
    points = Decimal(str(points))
    new_score = user.mri_score - points
    if new_score < MRI_FLOOR:
        new_score = MRI_FLOOR
    user.mri_score = new_score
    user.save(update_fields=['mri_score'])

    MriEvent.objects.create(
        user=user,
        delta=-points,
        reason=reason,
        description=description,
        reference_id=reference_id,
    )

    from notifications.models import Notification

    Notification.objects.create(
        user=user,
        title='MRI score updated',
        body=(
            f'You lost {points} MRI points: {description}. '
            f'Your score is now {new_score}.'
        ),
        notification_type='mri_update',
    )

    return new_score


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def user_response(user, request):
    return {
        'user': UserSerializer(user, context={'request': request}).data,
        'tokens': issue_tokens(user),
    }


def record_transaction(user, title, amount, transaction_type, is_credit, group=None):
    from blockchain.services import record_on_chain
    from ledger.models import Transaction

    transaction = Transaction.objects.create(
        user=user,
        group=group,
        title=title,
        amount=amount,
        transaction_type=transaction_type,
        status='completed',
        is_credit=is_credit,
    )
    record_on_chain(transaction)
    transaction.save(update_fields=['hash', 'status'])
    return transaction


def build_dashboard(user, request):
    from contributions.models import Contribution
    from groups.models import GroupMembership
    from ledger.models import Transaction
    from ledger.serializers import TransactionSerializer
    from loans.models import Loan

    memberships = GroupMembership.objects.filter(user=user).select_related('group')
    active_groups = memberships.count()

    contributions = Contribution.objects.filter(user=user)
    total_contributions = sum(c.amount for c in contributions.filter(status='completed'))
    pending_payments = contributions.filter(status__in=['outstanding', 'late', 'pending']).count()

    njangi_balance = sum(m.group.fund_balance for m in memberships)
    total_savings = float(user.wallet_balance) + float(total_contributions)

    active_loans = Loan.objects.filter(user=user, status='active')
    active_loans_amount = sum(l.remaining_balance for l in active_loans)

    next_contribution = (
        contributions.filter(status__in=['outstanding', 'pending'])
        .order_by('due_date')
        .first()
    )
    next_payment_date = (
        next_contribution.due_date if next_contribution
        else user.date_joined.date()
    )

    current_membership = memberships.filter(is_current_beneficiary=True).first()
    current_payout = (
        current_membership.group.contribution_amount * current_membership.group.max_members
        if current_membership else 0
    )

    social_fund_balance = sum(
        fund.balance
        for m in memberships
        for fund in m.group.social_funds.filter(is_active=True)
    )

    recent = Transaction.objects.filter(user=user).order_by('-created_at')[:5]
    recent_activity = TransactionSerializer(recent, many=True).data

    return {
        'njangi_balance': njangi_balance,
        'total_contributions': total_contributions,
        'next_payment_date': next_payment_date,
        'active_groups': active_groups,
        'pending_payments': pending_payments,
        'total_savings': total_savings,
        'active_loans_amount': active_loans_amount,
        'social_fund_balance': social_fund_balance,
        'current_payout': current_payout,
        'wallet_balance': user.wallet_balance,
        'savings_balance': user.savings_balance,
        'total_balance': user.wallet_balance + user.savings_balance,
        'mri_score': user.mri_score,
        'mri_trend': user.mri_trend,
        'mri_breakdown': {
            'payment_punctuality': user.mri_payment_punctuality,
            'attendance': user.mri_attendance,
            'loan_repayment': user.mri_loan_repayment,
            'contribution_consistency': user.mri_contribution_consistency,
            'community_participation': user.mri_community_participation,
        },
        'recent_activity': recent_activity,
    }
