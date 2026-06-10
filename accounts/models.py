import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=150)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    firebase_uid = models.CharField(max_length=128, blank=True, null=True, unique=True)

    mri_score = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    mri_trend = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    mri_payment_punctuality = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    mri_attendance = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    mri_loan_repayment = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    mri_contribution_consistency = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    mri_community_participation = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    badge = models.CharField(max_length=50, blank=True, default='')
    is_kyc_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    social_fund_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    wallet_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone', 'full_name']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.full_name

    @property
    def groups_count(self):
        return self.group_memberships.count()

    @property
    def years_active(self):
        delta = timezone.now() - self.date_joined
        return max(1, delta.days // 365)

    def recalculate_mri(self):
        scores = [
            self.mri_payment_punctuality,
            self.mri_attendance,
            self.mri_loan_repayment,
            self.mri_contribution_consistency,
            self.mri_community_participation,
        ]
        if any(float(s) > 0 for s in scores):
            self.mri_score = sum(float(s) for s in scores) / len(scores)
        self.save(update_fields=['mri_score'])
