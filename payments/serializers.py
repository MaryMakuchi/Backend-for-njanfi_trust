from rest_framework import serializers


class MomoWebhookSerializer(serializers.Serializer):
    """Payload shape for a (stubbed) MTN MoMo Collections payment notification.

    In production this would be replaced by MTN's actual callback schema;
    `external_id` is the value the backend supplied when it requested the
    payment (here, the Njangi Trust user's UUID).
    """

    reference_id = serializers.CharField()
    status = serializers.ChoiceField(choices=['SUCCESSFUL', 'FAILED', 'PENDING'])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(default='XAF')
    payer_phone = serializers.CharField()
    external_id = serializers.UUIDField(help_text='Njangi Trust user ID')
    purpose = serializers.ChoiceField(choices=['contribution', 'wallet_topup'])
    group_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs['purpose'] == 'contribution' and not attrs.get('group_id'):
            raise serializers.ValidationError('group_id is required when purpose is "contribution".')
        return attrs
