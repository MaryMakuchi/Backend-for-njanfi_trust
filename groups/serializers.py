import math
from decimal import Decimal

from rest_framework import serializers

from groups.models import (
    GroupMembership,
    GroupMessage,
    MembershipRequest,
    NjangiGroup,
    SavingsContribution,
    SavingsPeriod,
    SocialFund,
    SocialFundContribution,
)


def _validate_schedule(attrs):
    """Validate consistency of play-schedule fields when any are provided."""
    schedule_keys = ('play_weekday', 'play_week_of_month', 'play_deadline_time')
    has_schedule = any(attrs.get(k) is not None for k in schedule_keys)
    if not has_schedule:
        return
    if attrs.get('play_weekday') is None:
        raise serializers.ValidationError(
            {'play_weekday': 'play_weekday is required when a play schedule is set.'}
        )
    weekday = attrs.get('play_weekday')
    if weekday is not None and not (0 <= weekday <= 6):
        raise serializers.ValidationError(
            {'play_weekday': 'play_weekday must be between 0 (Monday) and 6 (Sunday).'}
        )
    frequency = attrs.get('play_frequency') or 'monthly'
    if frequency == 'monthly' and not attrs.get('play_week_of_month'):
        raise serializers.ValidationError(
            {'play_week_of_month': 'play_week_of_month is required for a monthly schedule.'}
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
    invitation_code = serializers.SerializerMethodField()
    next_play_due = serializers.SerializerMethodField()

    class Meta:
        model = NjangiGroup
        fields = [
            'id', 'name', 'member_count', 'max_members', 'contribution_amount',
            'frequency', 'fund_balance', 'cycle_progress', 'average_mri',
            'start_date', 'end_date', 'invitation_code', 'rules', 'members',
            'current_beneficiary_id', 'next_beneficiary_id', 'current_picker',
            'target_amount', 'duration_months', 'picking_mode',
            'schedule_generated', 'pickers_per_cycle', 'rotation_started',
            'play_frequency', 'play_weekday', 'play_week_of_month',
            'play_deadline_time', 'next_play_due',
        ]

    def get_next_play_due(self, obj):
        dt = obj.next_play_due_datetime()
        return dt.isoformat() if dt else None

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

    def get_invitation_code(self, obj):
        request = self.context.get('request')
        if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=request.user).first()
        if not membership or membership.role != 'president':
            return None
        return obj.invitation_code

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


class GroupSearchSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = NjangiGroup
        fields = ['id', 'name', 'member_count', 'max_members']


class CreateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = NjangiGroup
        fields = [
            'name', 'contribution_amount', 'frequency', 'max_members',
            'start_date', 'rules', 'target_amount', 'duration_months', 'picking_mode',
            'play_frequency', 'play_weekday', 'play_week_of_month', 'play_deadline_time',
        ]
        extra_kwargs = {
            'play_weekday': {'required': False, 'allow_null': True},
            'play_week_of_month': {'required': False, 'allow_null': True},
            'play_deadline_time': {'required': False, 'allow_null': True},
        }

    def validate_name(self, value):
        # Exact (case-sensitive) match: "Patty Crab" and "patty crab" are
        # treated as different names, but an identical name is rejected.
        if NjangiGroup.objects.filter(name=value).exists():
            raise serializers.ValidationError('A group with this name already exists.')
        return value

    def validate(self, attrs):
        _validate_schedule(attrs)
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
    mode = serializers.ChoiceField(choices=['random', 'manual', 'mri_weighted'])
    order = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate(self, attrs):
        # In mri_weighted mode the server computes the order from members' MRI,
        # so no client-supplied order is required.
        if attrs.get('mode') == 'mri_weighted':
            return attrs
        if not attrs.get('order'):
            raise serializers.ValidationError(
                'Provide an "order" list of member user IDs to assign the picking order. '
                'For random mode, shuffle the member list client-side and submit the result here for confirmation.'
            )
        return attrs


class UpdateGroupSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NjangiGroup
        fields = [
            'max_members', 'play_frequency', 'play_weekday',
            'play_week_of_month', 'play_deadline_time',
        ]
        extra_kwargs = {
            'play_frequency': {'required': False},
            'play_weekday': {'required': False, 'allow_null': True},
            'play_week_of_month': {'required': False, 'allow_null': True},
            'play_deadline_time': {'required': False, 'allow_null': True},
        }

    def validate_max_members(self, value):
        group = self.instance
        if group is not None and value < group.member_count:
            raise serializers.ValidationError(
                f'max_members cannot be less than the current member count ({group.member_count}).'
            )
        return value

    def validate(self, attrs):
        # Merge with existing instance values so partial schedule patches are
        # validated against the full resulting schedule.
        merged = {
            'play_frequency': attrs.get('play_frequency', getattr(self.instance, 'play_frequency', None)),
            'play_weekday': attrs.get('play_weekday', getattr(self.instance, 'play_weekday', None)),
            'play_week_of_month': attrs.get(
                'play_week_of_month', getattr(self.instance, 'play_week_of_month', None)
            ),
            'play_deadline_time': attrs.get(
                'play_deadline_time', getattr(self.instance, 'play_deadline_time', None)
            ),
        }
        _validate_schedule(merged)
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


class SavingsPeriodSerializer(serializers.ModelSerializer):
    is_closed = serializers.BooleanField(read_only=True)

    class Meta:
        model = SavingsPeriod
        fields = [
            'id', 'interest_rate', 'interest_type', 'start_date', 'end_date',
            'status', 'is_closed', 'created_at',
        ]


class StartSavingsPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsPeriod
        fields = ['interest_rate', 'interest_type', 'start_date', 'end_date']

    def validate(self, attrs):
        if attrs['end_date'] <= attrs['start_date']:
            raise serializers.ValidationError('end_date must be after start_date.')
        return attrs


PAYMENT_SOURCE_CHOICES = ['wallet', 'momo', 'bank']


class SavingsDepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    source = serializers.ChoiceField(choices=PAYMENT_SOURCE_CHOICES, default='wallet', required=False)


class PlayNjangiSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=PAYMENT_SOURCE_CHOICES, default='wallet', required=False)


class MembershipRequestSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = MembershipRequest
        fields = ['id', 'user', 'requested_at']

    def get_user(self, obj):
        return {'id': str(obj.user.id), 'name': obj.user.full_name}


class RespondMembershipRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['accept', 'reject'])


class GroupPreviewSerializer(serializers.ModelSerializer):
    """Safe public-facing preview for non-members deciding whether to join.

    Excludes invite code, member list, and all financial/ledger details.
    """

    member_count = serializers.IntegerField(read_only=True)
    next_play_due = serializers.SerializerMethodField()
    president_name = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    has_pending_request = serializers.SerializerMethodField()

    class Meta:
        model = NjangiGroup
        fields = [
            'id', 'name', 'rules', 'contribution_amount', 'max_members',
            'member_count', 'play_frequency', 'next_play_due',
            'president_name', 'is_member', 'has_pending_request',
        ]

    def get_next_play_due(self, obj):
        dt = obj.next_play_due_datetime()
        return dt.isoformat() if dt else None

    def get_president_name(self, obj):
        m = obj.memberships.select_related('user').filter(role='president').first()
        return m.user.full_name if m else None

    def get_is_member(self, obj):
        user = self.context['request'].user
        return obj.memberships.filter(user=user).exists()

    def get_has_pending_request(self, obj):
        user = self.context['request'].user
        return MembershipRequest.objects.filter(group=obj, user=user, status='pending').exists()
