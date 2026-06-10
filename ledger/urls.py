from django.urls import path

from ledger.views import TransactionListView

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
]
