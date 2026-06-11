import random

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
