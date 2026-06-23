from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from blockchain.services import record_on_chain
from contributions.models import Contribution
from groups.models import GroupMembership, NjangiGroup
from ledger.models import Transaction
from notifications.models import Notification
from payments.serializers import MomoWebhookSerializer


class MomoWebhookView(APIView):
    """Receives MTN MoMo Collections payment confirmations.

    This is a stub: it mimics the shape of a real MTN MoMo webhook so the
    rest of the pipeline (ledger recording -> notifications) can be
    exercised end-to-end. Swap in real signature verification once MTN
    sandbox credentials are available.

    Flow: MTN confirms payment -> this view records a Transaction ->
    Transaction is recorded on the Celo ledger -> group members are
    notified.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get('X-Momo-Signature', '')
        if signature != settings.MOMO_WEBHOOK_SECRET:
            return Response({'detail': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = MomoWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data['status'] != 'SUCCESSFUL':
            return Response({'detail': f'Payment {data["status"]}, no action taken.'})

        user = get_object_or_404(User, id=data['external_id'])
        amount = data['amount']

        if data['purpose'] == 'wallet_topup':
            transaction = self._handle_wallet_topup(user, amount, data['reference_id'])
        else:
            transaction = self._handle_contribution(user, amount, data['group_id'], data['reference_id'])

        return Response({
            'detail': 'Payment processed',
            'transaction_id': str(transaction.id),
            'transaction_hash': transaction.hash,
            'transaction_status': transaction.status,
        }, status=status.HTTP_201_CREATED)

    def _handle_wallet_topup(self, user, amount, reference_id):
        user.wallet_balance += amount
        user.save(update_fields=['wallet_balance'])

        transaction = Transaction.objects.create(
            user=user,
            title=f'MTN MoMo Top-up ({reference_id})',
            amount=amount,
            transaction_type='wallet_topup',
            status='completed',
            is_credit=True,
        )
        record_on_chain(transaction)
        transaction.save(update_fields=['hash', 'status'])

        Notification.objects.create(
            user=user,
            title='Wallet Top-up Received',
            body=f'Your Mobile Money payment of {amount:,.0f} CFA was confirmed and added to your wallet.',
            notification_type='contribution_confirmation',
            target_type='transaction',
            target_id=str(transaction.id),
        )
        return transaction

    def _handle_contribution(self, user, amount, group_id, reference_id):
        group = get_object_or_404(NjangiGroup, id=group_id)

        Contribution.objects.create(
            group=group,
            user=user,
            amount=amount,
            due_date=timezone.now().date(),
            status='completed',
            paid_date=timezone.now(),
            payment_method='mobile_money',
        )
        group.fund_balance += amount
        group.cycle_progress = min(group.cycle_progress + 1, group.max_members)
        group.save(update_fields=['fund_balance', 'cycle_progress'])

        transaction = Transaction.objects.create(
            user=user,
            group=group,
            title=f'Contribution - {group.name}',
            amount=amount,
            transaction_type='contribution',
            status='completed',
            is_credit=False,
        )
        record_on_chain(transaction)
        transaction.save(update_fields=['hash', 'status'])

        user.mri_contribution_consistency = min(float(user.mri_contribution_consistency) + 0.2, 10)
        user.mri_trend = 0.2
        user.recalculate_mri()

        Notification.objects.create(
            user=user,
            title='Contribution Confirmed',
            body=f'Your Mobile Money contribution of {amount:,.0f} CFA to {group.name} was confirmed.',
            notification_type='contribution_confirmation',
            target_type='transaction',
            target_id=str(transaction.id),
        )

        member_ids = GroupMembership.objects.filter(group=group).exclude(
            user=user,
        ).values_list('user_id', flat=True)
        Notification.objects.bulk_create([
            Notification(
                user_id=member_id,
                title='New Contribution',
                body=f'{user.full_name} contributed {amount:,.0f} CFA to {group.name}.',
                notification_type='group_announcement',
                target_type='group',
                target_id=str(group.id),
            )
            for member_id in member_ids
        ])

        return transaction
