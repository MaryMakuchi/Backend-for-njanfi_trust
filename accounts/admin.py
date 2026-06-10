from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('full_name', 'email', 'phone', 'mri_score', 'is_kyc_verified', 'is_staff')
    list_filter = ('is_kyc_verified', 'is_staff', 'phone_verified', 'email_verified')
    search_fields = ('full_name', 'email', 'phone')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('full_name', 'phone', 'profile_image', 'badge', 'firebase_uid')}),
        ('MRI', {'fields': (
            'mri_score', 'mri_trend', 'mri_payment_punctuality', 'mri_attendance',
            'mri_loan_repayment', 'mri_contribution_consistency', 'mri_community_participation',
        )}),
        ('Verification', {'fields': ('is_kyc_verified', 'phone_verified', 'email_verified')}),
        ('Balances', {'fields': ('wallet_balance', 'social_fund_balance')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone', 'full_name', 'password1', 'password2'),
        }),
    )
