import math
import secrets
import uuid

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models


class NjangiGroup(models.Model):
    FREQUENCY_CHOICES = [
        ('Weekly', 'Weekly'),
        ('Bi-weekly', 'Bi-weekly'),
        ('Monthly', 'Monthly'),
    ]

    PICKING_MODE_CHOICES = [
        ('random', 'Random'),
        ('manual', 'Manual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    contribution_amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='Monthly')
    max_members = models.PositiveIntegerField()
    start_date = models.DateField()
    rules = models.TextField(blank=True)
    invitation_code = models.CharField(max_length=20, unique=True, blank=True)
    fund_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cycle_progress = models.PositiveIntegerField(default=0)
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    duration_months = models.PositiveIntegerField(default=12)
    picking_mode = models.CharField(max_length=10, choices=PICKING_MODE_CHOICES, default='random')
    schedule_generated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invitation_code:
            self.invitation_code = secrets.token_hex(4).upper()[:8]
        super().save(*args, **kwargs)

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def average_mri(self):
        scores = self.memberships.select_related('user').values_list('user__mri_score', flat=True)
        scores = [float(s) for s in scores if s]
        return sum(scores) / len(scores) if scores else 0

    @property
    def pickers_per_cycle(self):
        if not self.duration_months:
            return 1
        return max(1, math.ceil(self.max_members / self.duration_months))

    @property
    def end_date(self):
        return self.start_date + relativedelta(months=self.duration_months)


class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ('president', 'President'),
        ('treasurer', 'Treasurer'),
        ('member', 'Member'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(NjangiGroup, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    rotation_position = models.PositiveIntegerField(null=True, blank=True)
    is_current_beneficiary = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')
        ordering = ['rotation_position', 'joined_at']

    def __str__(self):
        return f'{self.user.full_name} in {self.group.name}'

    @property
    def pick_cycle(self):
        if not self.rotation_position:
            return None
        return math.ceil(self.rotation_position / self.group.pickers_per_cycle)


class SocialFund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(NjangiGroup, on_delete=models.CASCADE, related_name='social_funds')
    reason = models.TextField()
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_social_funds',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Social Fund - {self.group.name}'


class SocialFundContribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_fund = models.ForeignKey(SocialFund, on_delete=models.CASCADE, related_name='contributions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='social_fund_contributions',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.full_name} -> {self.social_fund} ({self.amount})'
