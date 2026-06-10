import secrets
import uuid

from django.conf import settings
from django.db import models


class NjangiGroup(models.Model):
    FREQUENCY_CHOICES = [
        ('Weekly', 'Weekly'),
        ('Bi-weekly', 'Bi-weekly'),
        ('Monthly', 'Monthly'),
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
