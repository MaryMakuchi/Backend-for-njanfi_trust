from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.models import LinkedAccount, User
from accounts.serializers import (
    AmountSerializer,
    ChangePasswordSerializer,
    DashboardSerializer,
    ForgotPasswordSerializer,
    LinkedAccountSerializer,
    LoginSerializer,
    PhoneLoginSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyEmailSerializer,
    VerifyPhoneSerializer,
    WalletWithdrawSerializer,
)
from accounts.services import build_dashboard, record_transaction, user_response


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(user_response(user, request), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(user_response(serializer.validated_data['user'], request))


class PhoneLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PhoneLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(user_response(serializer.validated_data['user'], request))


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class VerifyPhoneView(APIView):
    def post(self, request):
        serializer = VerifyPhoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data['otp'] != '123456':
            return Response({'detail': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        user.phone_verified = True
        user.save(update_fields=['phone_verified'])
        return Response({'detail': 'Phone verified successfully'})


class VerifyEmailView(APIView):
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        return Response({'detail': 'Email verified successfully'})


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'detail': 'Password reset instructions sent if account exists.'})


class LogoutView(APIView):
    def post(self, request):
        return Response({'detail': 'Logged out successfully'})


class DashboardView(APIView):
    def get(self, request):
        data = build_dashboard(request.user, request)
        serializer = DashboardSerializer(data)
        return Response(serializer.data)


class JwtRefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Password updated successfully'})


class LinkedAccountListCreateView(generics.ListCreateAPIView):
    serializer_class = LinkedAccountSerializer

    def get_queryset(self):
        return LinkedAccount.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        return {'request': self.request}


class LinkedAccountDeleteView(generics.DestroyAPIView):
    serializer_class = LinkedAccountSerializer

    def get_queryset(self):
        return LinkedAccount.objects.filter(user=self.request.user)


class WalletTopUpView(APIView):
    def post(self, request):
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        user = request.user
        user.wallet_balance += amount
        user.save(update_fields=['wallet_balance'])
        record_transaction(user, 'Wallet Top-up', amount, 'wallet_topup', is_credit=True)
        return Response({'wallet_balance': user.wallet_balance})


class WalletWithdrawView(APIView):
    def post(self, request):
        serializer = WalletWithdrawSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        user = request.user
        if amount > user.wallet_balance:
            return Response({'amount': ['Insufficient wallet balance.']}, status=status.HTTP_400_BAD_REQUEST)

        user.wallet_balance -= amount
        user.save(update_fields=['wallet_balance'])
        record_transaction(user, 'Wallet Withdrawal', amount, 'wallet_withdrawal', is_credit=False)
        return Response({'wallet_balance': user.wallet_balance})


class SavingsDepositView(APIView):
    def post(self, request):
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        user = request.user
        if amount > user.wallet_balance:
            return Response({'amount': ['Insufficient wallet balance.']}, status=status.HTTP_400_BAD_REQUEST)

        user.wallet_balance -= amount
        user.savings_balance += amount
        user.save(update_fields=['wallet_balance', 'savings_balance'])
        record_transaction(user, 'Savings Deposit', amount, 'savings_deposit', is_credit=True)
        return Response({'wallet_balance': user.wallet_balance, 'savings_balance': user.savings_balance})


class SavingsWithdrawView(APIView):
    def post(self, request):
        serializer = AmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        user = request.user
        if amount > user.savings_balance:
            return Response({'amount': ['Insufficient savings balance.']}, status=status.HTTP_400_BAD_REQUEST)

        user.savings_balance -= amount
        user.wallet_balance += amount
        user.save(update_fields=['wallet_balance', 'savings_balance'])
        record_transaction(user, 'Savings Withdrawal', amount, 'savings_withdrawal', is_credit=False)
        return Response({'wallet_balance': user.wallet_balance, 'savings_balance': user.savings_balance})
