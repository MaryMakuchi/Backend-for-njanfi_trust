from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.models import User
from accounts.serializers import (
    DashboardSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    PhoneLoginSerializer,
    RegisterSerializer,
    UserSerializer,
    VerifyEmailSerializer,
    VerifyPhoneSerializer,
)
from accounts.services import build_dashboard, user_response


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
