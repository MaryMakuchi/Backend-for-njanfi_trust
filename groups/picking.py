"""Reliability-aware picking-order logic (MRI-gated early-payout mitigation).

In a rotating savings group the members who *receive the pot earliest* carry the
most default risk: they collect everyone's money before finishing their own
contributions, so a member who is likely to stop paying is most dangerous in an
early slot (classic moral hazard). This module biases the picking order so that
more reliable members (higher MRI) tend to receive earlier, and gates clearly
unreliable members out of the early window — but only when the group actually
has enough trusted members to do so, so brand-new groups (everyone at MRI 0)
are never artificially constrained.
"""
import math
import random
from decimal import Decimal

# Below this MRI (0-10 scale) a member is considered too risky for the early
# payout window, *provided* the group has enough higher-scoring members to fill
# that window without them.
EARLY_PAYOUT_MRI_FLOOR = Decimal('4.0')


def _mri(membership):
    return Decimal(membership.user.mri_score or 0)


def early_window_size(member_count):
    """How many of the earliest payout slots are treated as high-risk.

    Roughly the first half of the rotation — those receive the pot well before
    completing their contributions.
    """
    return max(1, math.ceil(member_count / 2))


def _weighted_shuffle(members):
    """Random shuffle weighted by MRI: higher score → more likely placed first.

    The +0.5 floor keeps members at MRI 0 in the draw (otherwise they'd have
    zero weight and never be placed).
    """
    pool = list(members)
    out = []
    while pool:
        weights = [float(_mri(m)) + 0.5 for m in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]
        out.append(chosen)
        pool.remove(chosen)
    return out


def _gate_enforceable(memberships):
    """True when there are enough trusted members to fill the early window."""
    window = early_window_size(len(memberships))
    eligible = sum(1 for m in memberships if _mri(m) >= EARLY_PAYOUT_MRI_FLOOR)
    return eligible >= window


def mri_weighted_order(memberships):
    """Compute a reliability-weighted picking order, returning member user IDs.

    When the gate is enforceable, all trusted members are placed (weighted)
    ahead of all risky ones, guaranteeing no risky member precedes a trusted
    one. Otherwise it degrades to a pure weighted shuffle.
    """
    members = list(memberships)
    if _gate_enforceable(members):
        eligible = [m for m in members if _mri(m) >= EARLY_PAYOUT_MRI_FLOOR]
        risky = [m for m in members if _mri(m) < EARLY_PAYOUT_MRI_FLOOR]
        ordered = _weighted_shuffle(eligible) + _weighted_shuffle(risky)
    else:
        ordered = _weighted_shuffle(members)
    return [m.user_id for m in ordered]


def gating_violations(order_user_ids, membership_by_user):
    """Names of low-MRI members placed in the early window.

    Returns an empty list when the gate isn't enforceable (so fresh or
    uniformly-low groups are never blocked).
    """
    memberships = list(membership_by_user.values())
    if not _gate_enforceable(memberships):
        return []

    window = early_window_size(len(memberships))
    violations = []
    for position, user_id in enumerate(order_user_ids, start=1):
        if position > window:
            break
        m = membership_by_user[user_id]
        if _mri(m) < EARLY_PAYOUT_MRI_FLOOR:
            violations.append(m.user.full_name)
    return violations
