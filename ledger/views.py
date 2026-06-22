from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from ledger.models import Transaction
from ledger.serializers import TransactionSerializer


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user).select_related('group')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        type_filter = self.request.query_params.get('type')
        if type_filter:
            qs = qs.filter(transaction_type__in=type_filter.split(','))
        return qs


# Maps the frontend-facing ledger category to the concrete Transaction.transaction_type
# strings actually written across the codebase.
CATEGORY_TYPE_MAP = {
    'njangi': ['contribution', 'payout'],
    'savings': ['savings_deposit', 'savings_withdrawal'],
    'loans': ['loan_disbursement', 'loan_repayment'],
    'social_fund': ['social_fund'],
}


class GroupLedgerView(generics.ListAPIView):
    """Group-scoped, category-filterable ledger.

    GET /api/v1/groups/<group_id>/ledger/?category=<njangi|savings|loans|social_fund|all>

    Returns every Transaction for the group (filtered by category), newest first,
    for any member of the group. Non-members receive 403.
    """

    serializer_class = TransactionSerializer

    def get_queryset(self):
        # Import locally to avoid coupling ledger import-time to the groups app.
        from groups.models import GroupMembership

        group_id = self.kwargs['group_id']

        membership = GroupMembership.objects.filter(
            group_id=group_id, user=self.request.user,
        ).first()
        if not membership:
            raise PermissionDenied('You are not a member of this group.')

        is_treasurer = membership.role in ('treasurer', 'president')

        qs = Transaction.objects.filter(group_id=group_id).select_related('group', 'user')

        category = self.request.query_params.get('category', 'all')
        if category and category != 'all':
            if category == 'savings' and not is_treasurer:
                raise PermissionDenied('Only the group treasurer can view savings transactions.')
            types = CATEGORY_TYPE_MAP.get(category)
            if types is not None:
                qs = qs.filter(transaction_type__in=types)
        else:
            # For 'all' category, exclude savings transactions for non-treasurers
            if not is_treasurer:
                savings_types = CATEGORY_TYPE_MAP.get('savings', [])
                qs = qs.exclude(transaction_type__in=savings_types)

        return qs.order_by('-created_at')
