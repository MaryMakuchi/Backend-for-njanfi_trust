from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from blockchain.services import record_on_chain
from contributions.models import Contribution
from contributions.serializers import ContributionSerializer, PayContributionSerializer
from groups.models import NjangiGroup
from ledger.models import Transaction
from ledger.serializers import TransactionSerializer


class ContributionListView(generics.ListAPIView):
    serializer_class = ContributionSerializer

    def get_queryset(self):
        return Contribution.objects.filter(user=self.request.user).select_related('group')


class PayContributionView(APIView):
    def post(self, request):
        serializer = PayContributionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = NjangiGroup.objects.get(id=data['group_id'])

        contribution = Contribution.objects.create(
            group=group,
            user=request.user,
            amount=data['amount'],
            due_date=timezone.now().date(),
            status='completed',
            paid_date=timezone.now(),
            payment_method=data['payment_method'],
        )
        group.fund_balance += data['amount']
        group.cycle_progress = min(group.cycle_progress + 1, group.max_members)
        group.save(update_fields=['fund_balance', 'cycle_progress'])

        transaction = Transaction.objects.create(
            user=request.user,
            group=group,
            title=f'Contribution - {group.name}',
            amount=data['amount'],
            transaction_type='contribution',
            status='completed',
            is_credit=False,
        )
        record_on_chain(transaction)
        transaction.save(update_fields=['hash', 'status'])

        user = request.user
        user.mri_contribution_consistency = min(float(user.mri_contribution_consistency) + 0.2, 10)
        user.mri_trend = 0.2
        user.recalculate_mri()

        return Response(TransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)
