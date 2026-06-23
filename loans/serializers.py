from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from loans.models import Loan, LoanVote
from loans.services import max_eligible_amount


class LoanVoteDetailSerializer(serializers.ModelSerializer):
    voter_name = serializers.CharField(source='voter.full_name', read_only=True)

    class Meta:
        model = LoanVote
        fields = ['voter_name', 'decision', 'voted_at']


class LoanSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True, default=None)
    group_id = serializers.UUIDField(source='group.id', read_only=True, default=None)
    total_repayable = serializers.SerializerMethodField()
    votes = LoanVoteDetailSerializer(many=True, read_only=True)

    def get_total_repayable(self, obj):
        from decimal import Decimal
        interest = obj.amount * (obj.interest_rate / Decimal('100'))
        return str(obj.amount + interest)

    class Meta:
        model = Loan
        fields = [
            'id', 'amount', 'purpose', 'duration_months', 'status',
            'interest_rate', 'remaining_balance', 'due_date', 'group_id',
            'group_name', 'approved_date', 'total_repayable', 'votes',
        ]


class RequestLoanSerializer(serializers.ModelSerializer):
    group_id = serializers.UUIDField(required=True, write_only=True)
    interest_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, default=Decimal('5.0'),
    )

    class Meta:
        model = Loan
        fields = ['amount', 'purpose', 'duration_months', 'group_id', 'interest_rate']

    def validate_amount(self, value):
        user = self.context['request'].user
        max_amount = max_eligible_amount(user)
        if value > max_amount:
            raise serializers.ValidationError(
                f'Requested amount exceeds your loan eligibility of {max_amount:,.0f} CFA.',
            )
        return value

    def validate_group_id(self, value):
        from groups.models import NjangiGroup
        group = NjangiGroup.objects.filter(id=value).first()
        if not group:
            raise serializers.ValidationError('A group is required to request a loan.')
        return value

    def validate(self, attrs):
        # Only the group treasurer can set a custom interest_rate.
        # Non-treasurers have any provided value discarded (default applies).
        user = self.context['request'].user
        group_id = attrs.get('group_id')
        if group_id:
            from groups.models import GroupMembership
            is_treasurer = GroupMembership.objects.filter(
                group_id=group_id, user=user, role='treasurer',
            ).exists()
            if not is_treasurer:
                attrs.pop('interest_rate', None)
        return attrs

    def create(self, validated_data):
        from groups.models import NjangiGroup

        group_id = validated_data.pop('group_id')
        user = self.context['request'].user
        group = NjangiGroup.objects.get(id=group_id)

        duration_months = validated_data['duration_months']
        today = timezone.now().date()

        loan = Loan.objects.create(
            user=user,
            group=group,
            status='pending',
            remaining_balance=0,
            due_date=today + timedelta(days=30 * duration_months),
            **validated_data,
        )

        return loan


class VoteLoanSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=LoanVote.DECISION_CHOICES)


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
        from ledger.models import Transaction

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
