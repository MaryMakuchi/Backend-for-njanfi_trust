from rest_framework import serializers

from loans.models import Loan


class LoanSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)

    class Meta:
        model = Loan
        fields = [
            'id', 'amount', 'purpose', 'duration_months', 'status',
            'interest_rate', 'remaining_balance', 'due_date', 'group_name', 'approved_date',
        ]


class RequestLoanSerializer(serializers.ModelSerializer):
    group_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Loan
        fields = ['amount', 'purpose', 'duration_months', 'group_id']

    def create(self, validated_data):
        group_id = validated_data.pop('group_id', None)
        user = self.context['request'].user
        group = None
        if group_id:
            from groups.models import NjangiGroup
            group = NjangiGroup.objects.filter(id=group_id).first()
        return Loan.objects.create(user=user, group=group, **validated_data)
