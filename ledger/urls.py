from django.urls import path

from ledger.views import GroupLedgerView, TransactionListView

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    path(
        'groups/<uuid:group_id>/ledger/',
        GroupLedgerView.as_view(),
        name='group-ledger',
    ),
]
