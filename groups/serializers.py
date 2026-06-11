import math
from decimal import Decimal

from rest_framework import serializers

from groups.models import (
    GroupMembership,
    GroupMessage,
    NjangiGroup,
    SocialFund,
    SocialFundContribution,
)


class GroupMemberSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source='user.id')
    name = serializers.CharField(source='user.full_name')
    mri_score = serializers.DecimalField(source='user.mri_score', max_digits=4, decimal_places=1)
    role = serializers.CharField()
    pick_cycle = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = [
            'id', 'name', 'role', 'mri_score', 'is_current_beneficiary',
            'rotation_position', 'pick_cycle',
        ]

    def get_pick_cycle(self, obj):
        return obj.pick_cycle


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    average_mri = serializers.SerializerMethodField()
    members = GroupMemberSerializer(source='memberships', many=True, read_only=True)
    current_beneficiary_id = serializers.SerializerMethodField()
    next_beneficiary_id = serializers.SerializerMethodField()
    current_picker = serializers.SerializerMethodField()
    pickers_per_cycle = serializers.IntegerField(read_only=True)
    end_date = serializers.DateField(read_only=True)

    class Meta:
        model = NjangiGroup
        fields = [
            'id', 'name', 'member_count', 'max_members', 'contribution_amount',
            'frequency', 'fund_balance', 'cycle_progress', 'average_mri',
            'start_date', 'end_date', 'invitation_code', 'rules', 'members',
            'current_beneficiary_id', 'next_beneficiary_id', 'current_picker',
            'target_amount', 'duration_months', 'picking_mode',
            'schedule_generated', 'pickers_per_cycle',
        ]

    def get_average_mri(self, obj):
        return round(obj.average_mri, 1)

    def get_current_beneficiary_id(self, obj):
        m = obj.memberships.filter(is_current_beneficiary=True).first()
        return str(m.user_id) if m else None

    def get_next_beneficiary_id(self, obj):
        current = obj.memberships.filter(is_current_beneficiary=True).first()
        if not current or not current.rotation_position:
            nxt = obj.memberships.order_by('rotation_position').first()
        else:
            nxt = obj.memberships.filter(
                rotation_position__gt=current.rotation_position,
            ).order_by('rotation_position').first()
        return str(nxt.user_id) if nxt else None

    def get_current_picker(self, obj):
        if not obj.schedule_generated:
            return None
        m = obj.memberships.select_related('user').filter(is_current_beneficiary=True).first()
        if not m:
            return None
        return {
            'id': str(m.user_id),
            'name': m.user.full_name,
            'rotation_position': m.rotation_position,
        }


class CreateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = NjangiGroup
        fields = [
            'name', 'contribution_amount', 'frequency', 'max_members',
            'start_date', 'rules', 'target_amount', 'duration_months', 'picking_mode',
        ]

    def validate(self, attrs):
        target_amount = attrs.get('target_amount')
        duration_months = attrs.get('duration_months') or 12
        max_members = attrs['max_members']
        contribution_amount = attrs['contribution_amount']

        if target_amount:
            pickers_per_cycle = max(1, math.ceil(max_members / duration_months))
            pool_per_cycle = contribution_amount * max_members
            required = target_amount * pickers_per_cycle
            if pool_per_cycle < required:
                raise serializers.ValidationError(
                    'The contribution amount is too low to fund the target payout amount '
                    f'for {pickers_per_cycle} picker(s) per cycle. '
                    f'Each cycle collects {pool_per_cycle:,.0f} CFA but needs {required:,.0f} CFA.',
                )
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        group = NjangiGroup.objects.create(created_by=user, **validated_data)
        GroupMembership.objects.create(
            group=group,
            user=user,
            role='president',
            rotation_position=1,
        )
        return group


class JoinGroupSerializer(serializers.Serializer):
    invitation_code = serializers.CharField(required=False)
    group_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if not attrs.get('invitation_code') and not attrs.get('group_id'):
            raise serializers.ValidationError('Provide invitation_code or group_id.')
        return attrs


class AssignPickingOrderSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=['random', 'manual'])
    order = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate(self, attrs):
        if attrs['mode'] == 'manual' and not attrs.get('order'):
            raise serializers.ValidationError('Provide an "order" list of user IDs for manual mode.')
        return attrs


class SocialFundContributionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = SocialFundContribution
        fields = ['id', 'user_name', 'amount', 'created_at']


class SocialFundSerializer(serializers.ModelSerializer):
    contributions = SocialFundContributionSerializer(many=True, read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = SocialFund
        fields = [
            'id', 'group_id', 'group_name', 'reason', 'target_amount', 'balance',
            'start_date', 'end_date', 'created_by_name', 'is_active', 'contributions',
        ]


class CreateSocialFundSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialFund
        fields = ['reason', 'target_amount', 'start_date', 'end_date']


class ContributeSocialFundSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))


class GroupMessageSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = GroupMessage
        fields = ['id', 'group_id', 'user_id', 'user_name', 'message', 'created_at']
        read_only_fields = ['id', 'group_id', 'user_id', 'user_name', 'created_at']

    def create(self, validated_data):
        return GroupMessage.objects.create(
            group=self.context['group'],
            user=self.context['request'].user,
            **validated_data,
        )
