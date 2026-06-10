from django.urls import path

from accounts.views import (
    DashboardView,
    ForgotPasswordView,
    JwtRefreshView,
    LoginView,
    LogoutView,
    MeView,
    PhoneLoginView,
    RegisterView,
    VerifyEmailView,
    VerifyPhoneView,
)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/login/phone/', PhoneLoginView.as_view(), name='auth-login-phone'),
    path('auth/verify-phone/', VerifyPhoneView.as_view(), name='auth-verify-phone'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/token/refresh/', JwtRefreshView.as_view(), name='token-refresh'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]
