from django.conf import settings
from rest_framework import serializers

from ledger.models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    type = serializers.CharField(source='transaction_type')
    date = serializers.DateTimeField(source='created_at')
    explorer_url = serializers.SerializerMethodField()
    on_chain = serializers.SerializerMethodField()
    initiated_by = serializers.CharField(source='user.full_name', read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = [
            'id', 'title', 'amount', 'type', 'status', 'date',
            'group_name', 'hash', 'is_credit', 'explorer_url', 'on_chain',
            'initiated_by',
        ]

    def get_on_chain(self, obj):
        return obj.status == 'verified' and obj.hash.startswith('0x') and len(obj.hash) == 66

    def get_explorer_url(self, obj):
        if self.get_on_chain(obj):
            return f'{settings.CELO_EXPLORER_BASE_URL}{obj.hash}'
        return None
