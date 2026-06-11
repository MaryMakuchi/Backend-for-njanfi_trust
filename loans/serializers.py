from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from ledger.models import Transaction
from loans.models import Loan
from loans.services import max_eligible_amount


class LoanSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    group_id = serializers.UUIDField(source='group.id', read_only=True, default=None)

    class Meta:
        model = Loan
        fields = [
            'id', 'amount', 'purpose', 'duration_months', 'status',
            'interest_rate', 'remaining_balance', 'due_date', 'group_id',
            'group_name', 'approved_date',
        ]


class RequestLoanSerializer(serializers.ModelSerializer):
    group_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Loan
        fields = ['amount', 'purpose', 'duration_months', 'group_id']

    def validate_amount(self, value):
        user = self.context['request'].user
        max_amount = max_eligible_amount(user)
        if value > max_amount:
            raise serializers.ValidationError(
                f'Requested amount exceeds your loan eligibility of {max_amount:,.0f} CFA.',
            )
        return value

    def create(self, validated_data):
        group_id = validated_data.pop('group_id', None)
        user = self.context['request'].user
        group = None
        if group_id:
            from groups.models import NjangiGroup
            group = NjangiGroup.objects.filter(id=group_id).first()

        amount = validated_data['amount']
        duration_months = validated_data['duration_months']
        today = timezone.now().date()

        loan = Loan.objects.create(
            user=user,
            group=group,
            status='active',
            remaining_balance=amount,
            approved_date=today,
            due_date=today + timedelta(days=30 * duration_months),
            **validated_data,
        )

        user.wallet_balance = user.wallet_balance + amount
        user.save(update_fields=['wallet_balance'])

        Transaction.objects.create(
            user=user,
            group=group,
            title=f'Loan Disbursement - {group.name}' if group else 'Loan Disbursement',
            amount=amount,
            transaction_type='loan_disbursement',
            status='completed',
            is_credit=True,
        )

        return loan


class RepayLoanSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)

    def validate(self, attrs):
        loan = self.context['loan']
        user = self.context['request'].user
        if loan.status != 'active':
            raise serializers.ValidationError('This loan is not active.')
        if attrs['amount'] > user.wallet_balance:
            raise serializers.ValidationError('Insufficient wallet balance.')
        return attrs

    def save(self, **kwargs):
        loan = self.context['loan']
        user = self.context['request'].user
        amount = min(self.validated_data['amount'], loan.remaining_balance)

        user.wallet_balance = user.wallet_balance - amount
        user.save(update_fields=['wallet_balance'])

        loan.remaining_balance = loan.remaining_balance - amount
        if loan.remaining_balance <= 0:
            loan.remaining_balance = 0
            loan.status = 'repaid'
        loan.save(update_fields=['remaining_balance', 'status'])

        Transaction.objects.create(
            user=user,
            group=loan.group,
            title=f'Loan Repayment - {loan.group.name}' if loan.group else 'Loan Repayment',
            amount=amount,
            transaction_type='loan_repayment',
            status='completed',
            is_credit=False,
        )

        return loan
