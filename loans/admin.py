from django.contrib import admin

from loans.models import Loan


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'purpose', 'remaining_balance', 'due_date')
    list_filter = ('status',)
