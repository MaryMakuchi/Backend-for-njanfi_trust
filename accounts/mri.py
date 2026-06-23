"""Fair, evidence-based Member Reliability Index (MRI) scoring.

This replaces the old flat-rate "demerit" system (which subtracted a fixed
number of points per incident). Instead of arbitrary fixed penalties, every
sub-score is *derived* from the member's actual history, so a deduction is:

* Proportional   – the more (and the more severe) the failures, the larger the
  drop. A single late payment dents the score far less than repeated misses.
* Fair           – members are only judged on obligations that have actually
  come due; upcoming, not-yet-due items never count against anyone.
* Recoverable    – because the score is recomputed from history, paying off an
  overdue contribution or loan lifts the score back up. Penalties are never
  permanent.

The five sub-scores (0-10) are combined with fixed weights into the headline
``mri_score``. Each recompute that changes the headline score writes an
``MriEvent`` (audit trail) and notifies the member.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

# Weights for the headline MRI score. Must sum to 1.
WEIGHTS = {
    'payment_punctuality': Decimal('0.25'),
    'contribution_consistency': Decimal('0.25'),
    'loan_repayment': Decimal('0.20'),
    'attendance': Decimal('0.15'),
    'community_participation': Decimal('0.15'),
}

# A change smaller than this (on the 0-10 scale) is treated as noise and does
# not generate an audit event / notification.
SIGNIFICANT_DELTA = Decimal('0.1')

TEN = Decimal('10')


def _q(value):
    """Clamp to 0-10 and round to one decimal place."""
    value = Decimal(value)
    if value < 0:
        value = Decimal('0')
    if value > TEN:
        value = TEN
    return value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def _contribution_scores(user, today):
    """Return (punctuality, consistency) derived from contribution history.

    Only contributions that have come due (or reached a terminal paid state)
    are considered. Weighting: on-time = 1.0, late = 0.5, missed = 0.0.
    """
    from contributions.models import Contribution

    contribs = Contribution.objects.filter(user=user)

    on_time = late = missed = 0
    for c in contribs:
        if c.status == 'completed':
            paid = getattr(c, 'paid_date', None)
            if paid is not None and c.due_date is not None and paid.date() > c.due_date:
                late += 1
            else:
                on_time += 1
        elif c.status == 'late':
            late += 1
        elif c.status in ('pending', 'outstanding'):
            # Only counts against the member once it is actually overdue.
            if c.due_date is not None and c.due_date < today:
                missed += 1

    considered = on_time + late + missed
    if considered == 0:
        return None, None  # No track record yet -> keep current sub-scores.

    punctuality = TEN * (Decimal(on_time) + Decimal('0.5') * Decimal(late)) / Decimal(considered)
    consistency = TEN * (Decimal(on_time) + Decimal(late)) / Decimal(considered)
    return _q(punctuality), _q(consistency)


def _loan_repayment_score(user, today):
    """Return a loan-repayment sub-score derived from loan history.

    Repaid loans count as good; active loans that are overdue with an
    outstanding balance count as defaults (severity grows the longer overdue).
    Not-yet-due active loans are neutral and ignored.
    """
    from loans.models import Loan

    loans = Loan.objects.filter(user=user)

    good = Decimal('0')
    bad = Decimal('0')
    considered = 0
    for loan in loans:
        if loan.status == 'repaid':
            good += Decimal('1')
            considered += 1
        elif loan.status == 'active' and loan.due_date and loan.due_date < today \
                and (loan.remaining_balance or 0) > 0:
            # Severity scales with how overdue the loan is (capped at 1.0).
            days_over = (today - loan.due_date).days
            severity = min(Decimal('1.0'), Decimal('0.4') + Decimal(days_over) / Decimal('90'))
            bad += severity
            considered += 1

    if considered == 0:
        return None  # No closed/overdue loans -> keep current sub-score.

    score = TEN * (good) / (good + bad) if (good + bad) > 0 else Decimal('0')
    return _q(score)


def compute_scores(user):
    """Compute the five sub-scores and the weighted headline score for a user.

    Sub-scores with no supporting data fall back to the member's current stored
    value, so members are never punished for the absence of history.
    """
    today = timezone.now().date()

    punctuality, consistency = _contribution_scores(user, today)
    loan_repayment = _loan_repayment_score(user, today)

    scores = {
        'payment_punctuality': punctuality if punctuality is not None
        else _q(user.mri_payment_punctuality),
        'contribution_consistency': consistency if consistency is not None
        else _q(user.mri_contribution_consistency),
        'loan_repayment': loan_repayment if loan_repayment is not None
        else _q(user.mri_loan_repayment),
        # Attendance & community participation are not derivable from financial
        # records, so the member's existing values are preserved.
        'attendance': _q(user.mri_attendance),
        'community_participation': _q(user.mri_community_participation),
    }

    headline = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return scores, _q(headline)


def _dominant_reason(user, today):
    """Pick the most relevant failure reason for the audit/notification text."""
    from contributions.models import Contribution
    from loans.models import Loan

    overdue_loan = Loan.objects.filter(
        user=user, status='active', due_date__lt=today, remaining_balance__gt=0,
    ).exists()
    if overdue_loan:
        return 'loan_default', 'an overdue loan with an outstanding balance'

    missed_contrib = Contribution.objects.filter(
        user=user, status__in=['pending', 'outstanding'], due_date__lt=today,
    ).exists()
    if missed_contrib:
        return 'missed_contribution', 'one or more overdue contributions'

    late_contrib = Contribution.objects.filter(user=user, status='late').exists()
    if late_contrib:
        return 'late_njangi', 'late njangi payments'

    return 'missed_contribution', 'recent reliability changes'


def recompute_mri(user, record_event=True):
    """Recompute and persist a user's MRI from their actual history.

    Returns the new headline score. When the headline score changes by a
    significant amount and ``record_event`` is True, an :class:`MriEvent` is
    written and (for decreases) the member is notified.
    """
    from accounts.models import MriEvent

    old_score = _q(user.mri_score)
    scores, headline = compute_scores(user)

    user.mri_payment_punctuality = scores['payment_punctuality']
    user.mri_contribution_consistency = scores['contribution_consistency']
    user.mri_loan_repayment = scores['loan_repayment']
    user.mri_attendance = scores['attendance']
    user.mri_community_participation = scores['community_participation']

    delta = headline - old_score
    user.mri_score = headline
    user.mri_trend = _signed(delta)
    user.save(update_fields=[
        'mri_score', 'mri_trend', 'mri_payment_punctuality',
        'mri_contribution_consistency', 'mri_loan_repayment',
        'mri_attendance', 'mri_community_participation',
    ])

    if record_event and abs(delta) >= SIGNIFICANT_DELTA:
        today = timezone.now().date()
        if delta < 0:
            reason, cause = _dominant_reason(user, today)
            description = (
                f'Your MRI dropped by {abs(delta)} points due to {cause}. '
                f'Paying off what is due will recover your score.'
            )
        else:
            reason = 'late_njangi'  # reused as a generic positive-recovery tag
            description = (
                f'Your MRI improved by {delta} points as your obligations were met.'
            )

        MriEvent.objects.create(
            user=user,
            delta=_signed(delta),
            reason=reason,
            description=description,
        )

        if delta < 0:
            from notifications.models import Notification

            Notification.objects.create(
                user=user,
                title='MRI score updated',
                body=description,
                notification_type='mri_update',
            )

    return headline


def _signed(delta):
    """Round a signed delta to the MriEvent decimal scale (max_digits=4, dp=1)."""
    return Decimal(delta).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
