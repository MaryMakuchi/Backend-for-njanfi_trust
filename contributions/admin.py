from django.contrib import admin

from contributions.models import Contribution


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'amount', 'status', 'due_date', 'payment_method')
    list_filter = ('status', 'payment_method')
