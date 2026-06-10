import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from groups.models import NjangiGroup


class Contribution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('late', 'Late'),
        ('outstanding', 'Outstanding'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(NjangiGroup, on_delete=models.CASCADE, related_name='contributions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contributions',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='outstanding')
    paid_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return f'{self.user.full_name} - {self.group.name} - {self.amount}'

    def mark_paid(self, payment_method):
        self.status = 'completed'
        self.paid_date = timezone.now()
        self.payment_method = payment_method
        self.save()
        self.group.fund_balance += self.amount
        self.group.cycle_progress = min(
            self.group.cycle_progress + 1,
            self.group.max_members,
        )
        self.group.save(update_fields=['fund_balance', 'cycle_progress'])
