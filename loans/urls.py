from django.urls import path

from loans.views import (
    LoanEligibilityView,
    LoanListView,
    LoanRepayView,
    LoanVoteView,
    PendingLoanVotesView,
    RequestLoanView,
)

urlpatterns = [
    path('loans/', LoanListView.as_view(), name='loan-list'),
    path('loans/eligibility/', LoanEligibilityView.as_view(), name='loan-eligibility'),
    path('loans/request/', RequestLoanView.as_view(), name='loan-request'),
    path('loans/pending-votes/', PendingLoanVotesView.as_view(), name='loan-pending-votes'),
    path('loans/<uuid:pk>/repay/', LoanRepayView.as_view(), name='loan-repay'),
    path('loans/<uuid:pk>/vote/', LoanVoteView.as_view(), name='loan-vote'),
]
