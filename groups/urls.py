from django.urls import path

from groups.views import (
    AssignPickingOrderView,
    ContributeSocialFundView,
    GroupDetailView,
    GroupListCreateView,
    GroupMessageListCreateView,
    JoinGroupView,
    SocialFundListCreateView,
)

urlpatterns = [
    path('groups/', GroupListCreateView.as_view(), name='group-list'),
    path('groups/join/', JoinGroupView.as_view(), name='group-join'),
    path('groups/<uuid:pk>/', GroupDetailView.as_view(), name='group-detail'),
    path('groups/<uuid:pk>/picking-order/', AssignPickingOrderView.as_view(), name='group-picking-order'),
    path('groups/<uuid:pk>/social-fund/', SocialFundListCreateView.as_view(), name='group-social-fund'),
    path(
        'groups/<uuid:pk>/social-fund/<uuid:fund_id>/contribute/',
        ContributeSocialFundView.as_view(),
        name='group-social-fund-contribute',
    ),
    path('groups/<uuid:pk>/messages/', GroupMessageListCreateView.as_view(), name='group-messages'),
]
