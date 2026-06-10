from rest_framework import serializers

from ledger.models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    type = serializers.CharField(source='transaction_type')
    date = serializers.DateTimeField(source='created_at')

    class Meta:
        model = Transaction
        fields = [
            'id', 'title', 'amount', 'type', 'status', 'date',
            'group_name', 'hash', 'is_credit',
        ]
