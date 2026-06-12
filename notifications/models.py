import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ('payment_reminder', 'Payment Reminder'),
        ('loan_approval', 'Loan Approval'),
        ('contribution_confirmation', 'Contribution Confirmation'),
        ('upcoming_payout', 'Upcoming Payout'),
        ('group_announcement', 'Group Announcement'),
        ('mri_update', 'MRI Update'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    notification_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    target_type = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=[
            ('group', 'Group'),
            ('loan', 'Loan'),
            ('transaction', 'Transaction'),
        ],
    )
    target_id = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
