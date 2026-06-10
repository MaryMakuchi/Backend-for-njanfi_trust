import uuid

from django.conf import settings
from django.db import models

from groups.models import NjangiGroup


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('contribution', 'Contribution'),
        ('payout', 'Payout'),
        ('loan_disbursement', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
        ('social_fund', 'Social Fund'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('verified', 'Verified'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    group = models.ForeignKey(
        NjangiGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions',
    )
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    hash = models.CharField(max_length=128, blank=True)
    is_credit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
