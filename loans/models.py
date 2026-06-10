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

    def __str__(self):
        return f'{self.user.full_name} - {self.amount} ({self.status})'
