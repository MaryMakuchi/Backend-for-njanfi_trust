from django.urls import path

from contributions.views import ContributionListView, PayContributionView

urlpatterns = [
    path('contributions/', ContributionListView.as_view(), name='contribution-list'),
    path('contributions/pay/', PayContributionView.as_view(), name='contribution-pay'),
]
