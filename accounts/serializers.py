from decimal import Decimal

from django.contrib.auth import authenticate
from rest_framework import serializers

from accounts.models import LinkedAccount, User


class UserSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    groups_count = serializers.IntegerField(read_only=True)
    years_active = serializers.IntegerField(read_only=True)
    global_rank = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'phone', 'profile_image_url',
            'mri_score', 'is_kyc_verified', 'groups_count', 'years_active',
            'global_rank', 'badge', 'wallet_balance', 'savings_balance',
        ]

    def get_profile_image_url(self, obj):
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None

    def get_global_rank(self, obj):
        higher = User.objects.filter(mri_score__gt=obj.mri_score, is_active=True).count()
        return higher + 1


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            email=attrs['email'],
            password=attrs['password'],
        )
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        attrs['user'] = user
        return attrs


class PhoneLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user = User.objects.get(phone=attrs['phone'])
        except User.DoesNotExist as exc:
            raise serializers.ValidationError('Invalid phone or password.') from exc
        if not user.check_password(attrs['password']):
            raise serializers.ValidationError('Invalid phone or password.')
        attrs['user'] = user
        return attrs


class OtpSerializer(serializers.Serializer):
    otp = serializers.CharField(min_length=6, max_length=6)


class VerifyPhoneSerializer(OtpSerializer):
    phone = serializers.CharField()


class VerifyEmailSerializer(OtpSerializer):
    email = serializers.EmailField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class MriBreakdownSerializer(serializers.Serializer):
    payment_punctuality = serializers.DecimalField(max_digits=4, decimal_places=1)
    attendance = serializers.DecimalField(max_digits=4, decimal_places=1)
    loan_repayment = serializers.DecimalField(max_digits=4, decimal_places=1)
    contribution_consistency = serializers.DecimalField(max_digits=4, decimal_places=1)
    community_participation = serializers.DecimalField(max_digits=4, decimal_places=1)


class DashboardSerializer(serializers.Serializer):
    njangi_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_contributions = serializers.DecimalField(max_digits=14, decimal_places=2)
    next_payment_date = serializers.DateField()
    active_groups = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    total_savings = serializers.DecimalField(max_digits=14, decimal_places=2)
    active_loans_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    social_fund_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    current_payout = serializers.DecimalField(max_digits=14, decimal_places=2)
    wallet_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    savings_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    mri_score = serializers.DecimalField(max_digits=4, decimal_places=1)
    mri_trend = serializers.DecimalField(max_digits=4, decimal_places=1)
    mri_breakdown = MriBreakdownSerializer()
    recent_activity = serializers.ListField()


class LinkedAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedAccount
        fields = ['id', 'account_type', 'provider', 'account_number', 'account_name', 'is_default']

    def create(self, validated_data):
        user = self.context['request'].user
        if validated_data.get('is_default'):
            LinkedAccount.objects.filter(user=user).update(is_default=False)
        return LinkedAccount.objects.create(user=user, **validated_data)


class AmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))


class WalletWithdrawSerializer(AmountSerializer):
    linked_account_id = serializers.UUIDField()

    def validate_linked_account_id(self, value):
        user = self.context['request'].user
        if not LinkedAccount.objects.filter(id=value, user=user).exists():
            raise serializers.ValidationError('Linked account not found.')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value
