from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import GroupMembership, NjangiGroup
from groups.serializers import CreateGroupSerializer, GroupSerializer, JoinGroupSerializer


class GroupListCreateView(generics.ListCreateAPIView):
    def get_queryset(self):
        return NjangiGroup.objects.filter(
            memberships__user=self.request.user,
        ).distinct().prefetch_related('memberships__user')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateGroupSerializer
        return GroupSerializer

    def perform_create(self, serializer):
        serializer.save()


class GroupDetailView(generics.RetrieveAPIView):
    serializer_class = GroupSerializer

    def get_queryset(self):
        return NjangiGroup.objects.filter(
            memberships__user=self.request.user,
        ).prefetch_related('memberships__user')


class JoinGroupView(APIView):
    def post(self, request):
        serializer = JoinGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data.get('invitation_code')
        group_id = serializer.validated_data.get('group_id')

        if code:
            group = NjangiGroup.objects.filter(invitation_code__iexact=code).first()
            if not group:
                return Response({'detail': 'Invalid invitation code'}, status=status.HTTP_404_NOT_FOUND)
        else:
            group = NjangiGroup.objects.filter(id=group_id).first()
            if not group:
                return Response({'detail': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

        if group.member_count >= group.max_members:
            return Response({'detail': 'Group is full'}, status=status.HTTP_400_BAD_REQUEST)

        if GroupMembership.objects.filter(group=group, user=request.user).exists():
            return Response({'detail': 'Already a member'}, status=status.HTTP_400_BAD_REQUEST)

        position = group.member_count + 1
        GroupMembership.objects.create(
            group=group,
            user=request.user,
            role='member',
            rotation_position=position,
        )
        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)
