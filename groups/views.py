import random

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import record_transaction
from groups.models import GroupMembership, GroupMessage, NjangiGroup, SocialFund, SocialFundContribution
from groups.serializers import (
    AssignPickingOrderSerializer,
    ContributeSocialFundSerializer,
    CreateGroupSerializer,
    CreateSocialFundSerializer,
    GroupMessageSerializer,
    GroupSerializer,
    JoinGroupSerializer,
    SocialFundSerializer,
)


class GroupListCreateView(generics.ListCreateAPIView):
    def get_queryset(self):
        return NjangiGroup.objects.filter(
            memberships__user=self.request.user,
        ).distinct().prefetch_related('memberships__user')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateGroupSerializer
        return GroupSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)


class GroupDetailView(generics.RetrieveAPIView):
    serializer_class = GroupSerializer

    def get_queryset(self):
        return NjangiGroup.objects.filter(
            memberships__user=self.request.user,
        ).prefetch_related('memberships__user')


class JoinGroupView(APIView):
    def post(self, request):
        serializer = JoinGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data.get('invitation_code')
        group_id = serializer.validated_data.get('group_id')

        if code:
            group = NjangiGroup.objects.filter(invitation_code__iexact=code).first()
            if not group:
                return Response({'detail': 'Invalid invitation code'}, status=status.HTTP_404_NOT_FOUND)
        else:
            group = NjangiGroup.objects.filter(id=group_id).first()
            if not group:
                return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        if group.member_count >= group.max_members:
            return Response({'detail': 'Group is full'}, status=status.HTTP_400_BAD_REQUEST)

        if GroupMembership.objects.filter(group=group, user=request.user).exists():
            return Response({'detail': 'Already a member'}, status=status.HTTP_400_BAD_REQUEST)

        position = group.member_count + 1
        GroupMembership.objects.create(
            group=group,
            user=request.user,
            role='member',
            rotation_position=position,
        )
        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)


class AssignPickingOrderView(APIView):
    def post(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can assign the picking order.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if group.member_count < group.max_members:
            return Response(
                {'detail': 'The group must be full before assigning the picking order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AssignPickingOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mode = serializer.validated_data['mode']
        memberships = list(group.memberships.all())

        if mode == 'random':
            order = [m.user_id for m in memberships]
            random.shuffle(order)
        else:
            order = serializer.validated_data['order']
            member_user_ids = {m.user_id for m in memberships}
            if set(order) != member_user_ids:
                return Response(
                    {'order': ['The order must include every member exactly once.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        membership_by_user = {m.user_id: m for m in memberships}
        for position, user_id in enumerate(order, start=1):
            m = membership_by_user[user_id]
            m.rotation_position = position
            m.is_current_beneficiary = position == 1
            m.save(update_fields=['rotation_position', 'is_current_beneficiary'])

        group.picking_mode = mode
        group.schedule_generated = True
        group.save(update_fields=['picking_mode', 'schedule_generated'])

        return Response(GroupSerializer(group).data)


class SocialFundListCreateView(generics.ListCreateAPIView):
    serializer_class = SocialFundSerializer

    def get_queryset(self):
        return SocialFund.objects.filter(
            group_id=self.kwargs['pk'],
            group__memberships__user=self.request.user,
        ).prefetch_related('contributions')

    def post(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can create a social fund.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateSocialFundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fund = SocialFund.objects.create(group=group, created_by=request.user, **serializer.validated_data)
        return Response(SocialFundSerializer(fund).data, status=status.HTTP_201_CREATED)


class ContributeSocialFundView(APIView):
    def post(self, request, pk, fund_id):
        fund = SocialFund.objects.filter(
            id=fund_id, group_id=pk, group__memberships__user=request.user,
        ).first()
        if not fund:
            return Response({'detail': 'Social fund not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ContributeSocialFundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        if amount > request.user.wallet_balance:
            return Response({'amount': ['Insufficient wallet balance.']}, status=status.HTTP_400_BAD_REQUEST)

        request.user.wallet_balance -= amount
        request.user.save(update_fields=['wallet_balance'])

        fund.balance += amount
        fund.save(update_fields=['balance'])

        SocialFundContribution.objects.create(social_fund=fund, user=request.user, amount=amount)
        record_transaction(
            request.user, f'Social Fund - {fund.group.name}', amount, 'social_fund', is_credit=False,
        )

        return Response(SocialFundSerializer(fund).data, status=status.HTTP_201_CREATED)


class PlayNjangiView(APIView):
    def post(self, request, pk):
        from contributions.models import Contribution
        from notifications.models import Notification

        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        if not group.schedule_generated:
            return Response(
                {'detail': 'Picking order has not been assigned yet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()
        already_played = Contribution.objects.filter(
            group=group, user=request.user, status='completed', due_date=today,
        ).exists()
        if already_played:
            return Response(
                {'detail': 'You have already played for this cycle.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = group.contribution_amount

        if amount > request.user.wallet_balance:
            return Response(
                {'detail': 'Insufficient wallet balance.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.wallet_balance -= amount
        request.user.save(update_fields=['wallet_balance'])

        contribution = Contribution.objects.create(
            group=group,
            user=request.user,
            amount=amount,
            due_date=today,
            status='pending',
        )
        contribution.mark_paid(payment_method='wallet')

        record_transaction(
            request.user, f'Contribution - {group.name}', amount, 'contribution', is_credit=False, group=group,
        )

        group.refresh_from_db()

        cycle_completed = False
        payout_data = None

        if group.cycle_progress >= group.max_members:
            cycle_completed = True
            current_membership = group.memberships.select_related('user').filter(
                is_current_beneficiary=True,
            ).first()

            payout_amount = group.contribution_amount * group.max_members

            if current_membership:
                recipient = current_membership.user
                recipient.wallet_balance += payout_amount
                recipient.save(update_fields=['wallet_balance'])

                payout_transaction = record_transaction(
                    recipient, f'Payout - {group.name}', payout_amount, 'payout', is_credit=True, group=group,
                )

                memberships = list(group.memberships.order_by('rotation_position'))
                current_position = current_membership.rotation_position
                next_membership = None
                if current_position is not None:
                    candidates = [
                        m for m in memberships
                        if m.rotation_position is not None and m.rotation_position > current_position
                    ]
                    if candidates:
                        next_membership = min(candidates, key=lambda m: m.rotation_position)
                    else:
                        positioned = [m for m in memberships if m.rotation_position is not None]
                        if positioned:
                            next_membership = min(positioned, key=lambda m: m.rotation_position)

                current_membership.is_current_beneficiary = False
                current_membership.save(update_fields=['is_current_beneficiary'])

                if next_membership:
                    next_membership.is_current_beneficiary = True
                    next_membership.save(update_fields=['is_current_beneficiary'])

                group.cycle_progress = 0
                group.fund_balance = 0
                group.save(update_fields=['cycle_progress', 'fund_balance'])

                payout_data = {
                    'amount': str(payout_amount),
                    'recipient': {
                        'id': str(recipient.id),
                        'name': recipient.full_name,
                    },
                    'transaction_hash': payout_transaction.hash or None,
                }

                Notification.objects.create(
                    user=recipient,
                    title=f'You received the payout for {group.name}',
                    body=f'You have received a payout of {payout_amount} from {group.name}.',
                    notification_type='upcoming_payout',
                )

                if next_membership:
                    other_members = group.memberships.exclude(
                        user_id=recipient.id,
                    ).select_related('user')
                    notifications = [
                        Notification(
                            user=m.user,
                            title=f'{group.name} cycle completed',
                            body=(
                                f'The current cycle for {group.name} has been completed and '
                                f'{recipient.full_name} received the payout. '
                                f'{next_membership.user.full_name} picks next.'
                            ),
                            notification_type='group_announcement',
                        )
                        for m in other_members
                    ]
                    if notifications:
                        Notification.objects.bulk_create(notifications)

        group.refresh_from_db()

        new_current = group.memberships.select_related('user').filter(
            is_current_beneficiary=True,
        ).first()
        current_picker_data = None
        if new_current:
            current_picker_data = {
                'id': str(new_current.user_id),
                'name': new_current.user.full_name,
                'rotation_position': new_current.rotation_position,
            }

        return Response(
            {
                'amount': str(amount),
                'group_fund_balance': str(group.fund_balance),
                'cycle_progress': group.cycle_progress,
                'max_members': group.max_members,
                'current_picker': current_picker_data,
                'cycle_completed': cycle_completed,
                'payout': payout_data,
            },
            status=status.HTTP_201_CREATED,
        )


class GroupMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = GroupMessageSerializer

    def get_group(self):
        return NjangiGroup.objects.filter(
            id=self.kwargs['pk'], memberships__user=self.request.user,
        ).first()

    def get_queryset(self):
        group = self.get_group()
        if not group:
            return GroupMessage.objects.none()
        return GroupMessage.objects.filter(group=group).select_related('user')

    def create(self, request, *args, **kwargs):
        group = self.get_group()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data, context={'request': request, 'group': group})
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(GroupMessageSerializer(message).data, status=status.HTTP_201_CREATED)
