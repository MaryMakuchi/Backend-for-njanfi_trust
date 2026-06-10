from rest_framework import serializers

from groups.models import GroupMembership, NjangiGroup


class GroupMemberSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source='user.id')
    name = serializers.CharField(source='user.full_name')
    mri_score = serializers.DecimalField(source='user.mri_score', max_digits=4, decimal_places=1)
    role = serializers.CharField()

    class Meta:
        model = GroupMembership
        fields = ['id', 'name', 'role', 'mri_score', 'is_current_beneficiary', 'rotation_position']


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    average_mri = serializers.SerializerMethodField()
    members = GroupMemberSerializer(source='memberships', many=True, read_only=True)
    current_beneficiary_id = serializers.SerializerMethodField()
    next_beneficiary_id = serializers.SerializerMethodField()

    class Meta:
        model = NjangiGroup
        fields = [
            'id', 'name', 'member_count', 'max_members', 'contribution_amount',
            'frequency', 'fund_balance', 'cycle_progress', 'average_mri',
            'start_date', 'invitation_code', 'rules', 'members',
            'current_beneficiary_id', 'next_beneficiary_id',
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


class CreateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = NjangiGroup
        fields = [
            'name', 'contribution_amount', 'frequency', 'max_members',
            'start_date', 'rules',
        ]

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
