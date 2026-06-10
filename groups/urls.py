from django.urls import path

from groups.views import GroupDetailView, GroupListCreateView, JoinGroupView

urlpatterns = [
    path('groups/', GroupListCreateView.as_view(), name='group-list'),
    path('groups/join/', JoinGroupView.as_view(), name='group-join'),
    path('groups/<uuid:pk>/', GroupDetailView.as_view(), name='group-detail'),
]
