from rest_framework import generics

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
