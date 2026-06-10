from rest_framework import serializers

from contributions.models import Contribution
from groups.models import NjangiGroup


class ContributionSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    group_id = serializers.UUIDField(source='group.id', read_only=True)

    class Meta:
        model = Contribution
        fields = [
            'id', 'group_id', 'group_name', 'amount', 'due_date',
            'status', 'paid_date', 'payment_method',
        ]


class PayContributionSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.CharField(max_length=50)

    def validate_group_id(self, value):
        user = self.context['request'].user
        if not NjangiGroup.objects.filter(id=value, memberships__user=user).exists():
            raise serializers.ValidationError('Group not found or not a member.')
        return value
