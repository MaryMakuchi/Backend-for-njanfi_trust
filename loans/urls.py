from django.urls import path

from loans.views import LoanEligibilityView, LoanListView, LoanRepayView, RequestLoanView

urlpatterns = [
    path('loans/', LoanListView.as_view(), name='loan-list'),
    path('loans/eligibility/', LoanEligibilityView.as_view(), name='loan-eligibility'),
    path('loans/request/', RequestLoanView.as_view(), name='loan-request'),
    path('loans/<uuid:pk>/repay/', LoanRepayView.as_view(), name='loan-repay'),
]
