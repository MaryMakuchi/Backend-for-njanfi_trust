from django.contrib import admin

from ledger.models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'transaction_type', 'status', 'created_at')
    list_filter = ('transaction_type', 'status')
