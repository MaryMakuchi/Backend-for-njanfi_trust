from decimal import Decimal

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import record_transaction
from groups.models import (
    GroupMembership,
    GroupMessage,
    MembershipRequest,
    NjangiGroup,
    SavingsContribution,
    SavingsPeriod,
    SocialFund,
    SocialFundContribution,
    compute_interest,
)
from groups.serializers import (
    AssignPickingOrderSerializer,
    ContributeSocialFundSerializer,
    CreateGroupSerializer,
    CreateSocialFundSerializer,
    GroupMessageSerializer,
    GroupSerializer,
    JoinGroupSerializer,
    MembershipRequestSerializer,
    RespondMembershipRequestSerializer,
    SavingsDepositSerializer,
    SavingsPeriodSerializer,
    SocialFundSerializer,
    StartSavingsPeriodSerializer,
    UpdateGroupSettingsSerializer,
)
from notifications.models import Notification


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


class GroupDetailView(generics.RetrieveUpdateAPIView):
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        return NjangiGroup.objects.filter(
            memberships__user=self.request.user,
        ).prefetch_related('memberships__user')

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UpdateGroupSettingsSerializer
        return GroupSerializer

    def patch(self, request, *args, **kwargs):
        group = self.get_object()
        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can edit group settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UpdateGroupSettingsSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(GroupSerializer(group).data)


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

        if GroupMembership.objects.filter(group=group, user=request.user).exists():
            return Response(
                {'detail': 'You are already a member of this group.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        if MembershipRequest.objects.filter(group=group, user=request.user, status='pending').exists():
            return Response(
                {'detail': 'Your membership request is already pending.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        if group.member_count >= group.max_members:
            return Response({'detail': 'This group is full.'}, status=status.HTTP_400_BAD_REQUEST)

        MembershipRequest.objects.create(group=group, user=request.user, status='pending')

        president = GroupMembership.objects.filter(group=group, role='president').select_related('user').first()
        if president:
            Notification.objects.create(
                user=president.user,
                title=f'New membership request for {group.name}',
                body=f'{request.user.full_name} has requested to join {group.name}.',
                notification_type='group_announcement',
                target_type='group',
                target_id=str(group.id),
            )

        return Response(
            {'detail': 'Membership request sent. Waiting for approval.'}, status=status.HTTP_201_CREATED,
        )


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

        if group.member_count < 2:
            return Response(
                {'detail': 'At least two members are required before assigning the picking order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AssignPickingOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mode = serializer.validated_data['mode']
        order = serializer.validated_data['order']
        memberships = list(group.memberships.all())

        member_user_ids = {m.user_id for m in memberships}
        order_set = set(order)
        if len(order) != len(order_set):
            return Response(
                {'order': ['The order must not contain duplicate members.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not order_set.issubset(member_user_ids):
            return Response(
                {'order': ['The order may only include current members of the group.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership_by_user = {m.user_id: m for m in memberships}

        # Assign positions for members included in the order.
        for position, user_id in enumerate(order, start=1):
            m = membership_by_user[user_id]
            m.rotation_position = position
            m.is_current_beneficiary = position == 1
            m.save(update_fields=['rotation_position', 'is_current_beneficiary'])

        # Any current members not included in the order are left out of the
        # active rotation until the picking order is re-run.
        for user_id, m in membership_by_user.items():
            if user_id not in order_set:
                m.rotation_position = None
                m.is_current_beneficiary = False
                m.save(update_fields=['rotation_position', 'is_current_beneficiary'])

        # Re-running the picking order changes the rotation, so reset cycle
        # progress and the accumulated fund balance for the new rotation.
        group.picking_mode = mode
        group.schedule_generated = True
        group.cycle_progress = 0
        group.fund_balance = 0
        group.save(update_fields=['picking_mode', 'schedule_generated', 'cycle_progress', 'fund_balance'])

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
                    target_type='group',
                    target_id=str(group.id),
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
                            target_type='group',
                            target_id=str(group.id),
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


def _user_savings_summary(period, user):
    contributions = SavingsContribution.objects.filter(period=period, user=user).order_by('created_at')
    principal = sum((c.amount for c in contributions), Decimal('0'))
    interest = sum((compute_interest(c, period) for c in contributions), Decimal('0'))
    interest = interest.quantize(Decimal('0.01'))
    total = (principal + interest).quantize(Decimal('0.01'))
    return {
        'principal': str(principal.quantize(Decimal('0.01'))),
        'interest_accrued': str(interest),
        'total': str(total),
        'deposits': [
            {'amount': str(c.amount), 'date': c.created_at.date().isoformat()}
            for c in contributions
        ],
    }


class StartSavingsPeriodView(APIView):
    def post(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can start a savings period.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        existing = SavingsPeriod.objects.filter(group=group).order_by('-created_at').first()
        if existing and not existing.is_closed:
            return Response(
                {'detail': 'An active savings period already exists for this group.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = StartSavingsPeriodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period = SavingsPeriod.objects.create(
            group=group,
            started_by=request.user,
            status='active',
            **serializer.validated_data,
        )

        members = GroupMembership.objects.filter(group=group).select_related('user')
        notifications = [
            Notification(
                user=m.user,
                title=f'New savings period for {group.name}',
                body=(
                    f'A new savings period has started for {group.name}: '
                    f'{period.interest_rate}% {period.interest_type} interest, '
                    f'from {period.start_date} to {period.end_date}.'
                ),
                notification_type='group_announcement',
                target_type='group',
                target_id=str(group.id),
            )
            for m in members
        ]
        if notifications:
            Notification.objects.bulk_create(notifications)

        return Response(SavingsPeriodSerializer(period).data, status=status.HTTP_201_CREATED)


class GroupSavingsView(APIView):
    def get(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        period = SavingsPeriod.objects.filter(group=group).order_by('-created_at').first()
        if not period:
            return Response({'period': None, 'my_savings': None})

        my_savings = _user_savings_summary(period, request.user)
        return Response({
            'period': SavingsPeriodSerializer(period).data,
            'my_savings': my_savings,
        })


class SavingsDepositView(APIView):
    def post(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        period = SavingsPeriod.objects.filter(group=group).order_by('-created_at').first()
        if not period or period.is_closed:
            return Response(
                {'detail': 'There is no active savings period for this group.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SavingsDepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        if amount > request.user.wallet_balance:
            return Response({'detail': 'Insufficient wallet balance.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.wallet_balance -= amount
        request.user.save(update_fields=['wallet_balance'])

        SavingsContribution.objects.create(period=period, user=request.user, amount=amount)
        record_transaction(
            request.user,
            title=f'Savings deposit - {group.name}',
            amount=amount,
            transaction_type='savings_deposit',
            is_credit=False,
            group=group,
        )

        return Response(_user_savings_summary(period, request.user), status=status.HTTP_201_CREATED)


class SavingsWithdrawView(APIView):
    def post(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        period = SavingsPeriod.objects.filter(group=group).order_by('-created_at').first()
        if not period or not period.is_closed:
            return Response(
                {'detail': 'Savings cannot be withdrawn until the savings period ends.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contributions = SavingsContribution.objects.filter(period=period, user=request.user)
        principal = sum((c.amount for c in contributions), Decimal('0'))
        interest = sum((compute_interest(c, period) for c in contributions), Decimal('0'))
        total = (principal + interest).quantize(Decimal('0.01'))

        if total <= 0:
            return Response({'detail': 'You have no savings to withdraw.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.wallet_balance += total
        request.user.save(update_fields=['wallet_balance'])

        record_transaction(
            request.user,
            title=f'Savings withdrawal - {group.name}',
            amount=total,
            transaction_type='savings_withdrawal',
            is_credit=True,
            group=group,
        )

        contributions.delete()

        return Response({
            'amount_withdrawn': str(total),
            'new_wallet_balance': str(request.user.wallet_balance),
        })


class CloseSavingsPeriodView(APIView):
    def post(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can start a savings period.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        period = SavingsPeriod.objects.filter(group=group, status='active').order_by('-created_at').first()
        if not period:
            return Response(
                {'detail': 'There is no active savings period for this group.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period.status = 'closed'
        period.save(update_fields=['status'])

        members = GroupMembership.objects.filter(group=group).select_related('user')
        notifications = [
            Notification(
                user=m.user,
                title=f'Savings period closed for {group.name}',
                body=(
                    f'The savings period for {group.name} has been closed. '
                    f'You can now withdraw your savings and accrued interest.'
                ),
                notification_type='group_announcement',
                target_type='group',
                target_id=str(group.id),
            )
            for m in members
        ]
        if notifications:
            Notification.objects.bulk_create(notifications)

        return Response(SavingsPeriodSerializer(period).data)


class MembershipRequestListView(APIView):
    def get(self, request, pk):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can view membership requests.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        requests = MembershipRequest.objects.filter(group=group, status='pending').select_related('user')
        return Response(MembershipRequestSerializer(requests, many=True).data)


class RespondMembershipRequestView(APIView):
    def post(self, request, pk, req_id):
        group = NjangiGroup.objects.filter(id=pk, memberships__user=request.user).first()
        if not group:
            return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'president':
            return Response(
                {'detail': 'Only the group president can respond to membership requests.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership_request = MembershipRequest.objects.filter(
            id=req_id, group=group, status='pending',
        ).select_related('user').first()
        if not membership_request:
            return Response({'detail': 'Membership request not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RespondMembershipRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data['decision']

        if decision == 'accept':
            if group.member_count >= group.max_members:
                return Response({'detail': 'This group is full.'}, status=status.HTTP_400_BAD_REQUEST)

            position = group.member_count + 1
            GroupMembership.objects.create(
                group=group,
                user=membership_request.user,
                role='member',
                rotation_position=position,
            )
            membership_request.status = 'accepted'
            membership_request.decided_at = timezone.now()
            membership_request.save(update_fields=['status', 'decided_at'])

            Notification.objects.create(
                user=membership_request.user,
                title=f'Welcome to {group.name}!',
                body=f'Your request to join {group.name} has been accepted. You are now a member.',
                notification_type='group_announcement',
                target_type='group',
                target_id=str(group.id),
            )
            return Response({'status': 'accepted'})

        membership_request.status = 'rejected'
        membership_request.decided_at = timezone.now()
        membership_request.save(update_fields=['status', 'decided_at'])

        Notification.objects.create(
            user=membership_request.user,
            title=f'Membership request to {group.name} declined',
            body=f'Your request to join {group.name} has been rejected.',
            notification_type='group_announcement',
            target_type='group',
            target_id=str(group.id),
        )
        return Response({'status': 'rejected'})
