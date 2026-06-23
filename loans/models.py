import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from groups.models import NjangiGroup


class Loan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('repaid', 'Repaid'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loans')
    group = models.ForeignKey(
        NjangiGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='loans',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.CharField(max_length=200)
    duration_months = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.0'))
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def total_repayable(self):
        """Return principal + simple interest."""
        interest = self.amount * (self.interest_rate / Decimal('100'))
        return self.amount + interest

    def __str__(self):
        return f'{self.user.full_name} - {self.amount} ({self.status})'


class LoanVote(models.Model):
    DECISION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loan_votes')
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('loan', 'voter')
        ordering = ['-voted_at']

    def __str__(self):
        return f'{self.voter.full_name} -> {self.loan_id} ({self.decision})'
