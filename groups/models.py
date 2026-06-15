import math
import secrets
import uuid
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class NjangiGroup(models.Model):
    FREQUENCY_CHOICES = [
        ('Weekly', 'Weekly'),
        ('Bi-weekly', 'Bi-weekly'),
        ('Monthly', 'Monthly'),
    ]

    PICKING_MODE_CHOICES = [
        ('random', 'Random'),
        ('manual', 'Manual'),
        ('mri_weighted', 'Reliability (MRI) weighted'),
    ]

    PLAY_FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    WEEK_OF_MONTH_CHOICES = [
        ('first', 'First'),
        ('second', 'Second'),
        ('third', 'Third'),
        ('fourth', 'Fourth'),
        ('last', 'Last'),
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
    picking_mode = models.CharField(max_length=20, choices=PICKING_MODE_CHOICES, default='random')
    schedule_generated = models.BooleanField(default=False)
    rotation_started = models.BooleanField(default=False)
    # Recurring njangi play schedule. Note: the existing ``frequency`` field
    # (Weekly/Bi-weekly/Monthly, title-case) is a free-form descriptor kept for
    # backwards compatibility with existing clients. ``play_frequency`` is the
    # machine-readable schedule driver used by next_play_due_datetime().
    play_frequency = models.CharField(
        max_length=10, choices=PLAY_FREQUENCY_CHOICES, default='monthly',
    )
    play_weekday = models.IntegerField(null=True, blank=True)  # 0=Mon..6=Sun (date.weekday())
    play_week_of_month = models.CharField(
        max_length=10, choices=WEEK_OF_MONTH_CHOICES, null=True, blank=True,
    )
    play_deadline_time = models.TimeField(null=True, blank=True)
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

    @staticmethod
    def _nth_weekday_of_month(year, month, weekday, week_of_month):
        """Return the date of the given weekday-of-month, or None if it doesn't
        exist (e.g. a 'fourth' that overflows is clamped; 'last' always valid)."""
        import calendar
        from datetime import date

        first = date(year, month, 1)
        first_weekday = first.weekday()
        # day-of-month of the first occurrence of `weekday`
        offset = (weekday - first_weekday) % 7
        first_occurrence_day = 1 + offset
        days_in_month = calendar.monthrange(year, month)[1]

        if week_of_month == 'last':
            day = first_occurrence_day
            while day + 7 <= days_in_month:
                day += 7
            return date(year, month, day)

        index = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3}.get(week_of_month, 0)
        day = first_occurrence_day + index * 7
        if day > days_in_month:
            return None
        return date(year, month, day)

    def next_play_due_datetime(self, from_dt=None):
        """Compute the next play-due datetime from the recurring schedule.

        Returns a timezone-aware datetime, or None if the schedule is not set.
        """
        from datetime import datetime, time, timedelta

        if self.play_weekday is None:
            return None
        deadline = self.play_deadline_time or time(23, 59)

        if from_dt is None:
            from_dt = timezone.now()
        tz = timezone.get_current_timezone()
        if timezone.is_aware(from_dt):
            local_now = timezone.localtime(from_dt, tz)
        else:
            local_now = timezone.make_aware(from_dt, tz)

        def make_aware(d):
            return timezone.make_aware(datetime.combine(d, deadline), tz)

        if self.play_frequency == 'weekly':
            days_ahead = (self.play_weekday - local_now.weekday()) % 7
            candidate_date = (local_now + timedelta(days=days_ahead)).date()
            candidate = make_aware(candidate_date)
            if candidate <= local_now:
                candidate = make_aware(candidate_date + timedelta(days=7))
            return candidate

        # monthly
        week = self.play_week_of_month or 'first'
        year, month = local_now.year, local_now.month
        for _ in range(13):
            d = self._nth_weekday_of_month(year, month, self.play_weekday, week)
            if d is not None:
                candidate = make_aware(d)
                if candidate > local_now:
                    return candidate
            month += 1
            if month > 12:
                month = 1
                year += 1
        return None


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


class GroupMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(NjangiGroup, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_messages',
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user.full_name} in {self.group.name}: {self.message[:30]}'


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


class SavingsPeriod(models.Model):
    INTEREST_TYPE_CHOICES = [
        ('simple', 'Simple'),
        ('compound', 'Compound'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(NjangiGroup, on_delete=models.CASCADE, related_name='savings_periods')
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='started_savings_periods',
    )
    interest_rate = models.DecimalField(max_digits=6, decimal_places=2)
    interest_type = models.CharField(max_length=10, choices=INTEREST_TYPE_CHOICES, default='simple')
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Savings period for {self.group.name} ({self.start_date} - {self.end_date})'

    @property
    def is_closed(self):
        return self.status == 'closed' or self.end_date < timezone.now().date()

    @property
    def total_months(self):
        months = (self.end_date.year - self.start_date.year) * 12 + (self.end_date.month - self.start_date.month)
        return max(1, months)


class SavingsContribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.ForeignKey(SavingsPeriod, on_delete=models.CASCADE, related_name='contributions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='savings_contributions',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.full_name} -> {self.period} ({self.amount})'

    def interest_accrued(self):
        return compute_interest(self, self.period)


def compute_interest(contribution, period):
    today = timezone.now().date()
    end = min(today, period.end_date)
    days_held = (end - contribution.created_at.date()).days
    days_held = max(0, days_held)

    period_total_days = (period.end_date - period.start_date).days
    period_total_days = max(1, period_total_days)

    rate = period.interest_rate
    amount = contribution.amount

    if period.interest_type == 'compound':
        monthly_rate = float(rate / Decimal('100')) / float(period.total_months)
        months_held = days_held / 30.0
        growth = (1 + monthly_rate) ** months_held - 1
        interest = amount * Decimal(str(growth))
    else:
        interest = amount * (rate / Decimal('100')) * (Decimal(days_held) / Decimal(period_total_days))

    return interest.quantize(Decimal('0.01'))


class MembershipRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(NjangiGroup, on_delete=models.CASCADE, related_name='membership_requests')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membership_requests',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f'{self.user.full_name} -> {self.group.name} ({self.status})'
