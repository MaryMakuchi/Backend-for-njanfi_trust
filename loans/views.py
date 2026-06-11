from django.utils import timezone
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import record_transaction
from groups.models import GroupMembership
from loans.models import Loan, LoanVote
from loans.serializers import (
    LoanSerializer,
    RepayLoanSerializer,
    RequestLoanSerializer,
    VoteLoanSerializer,
)
from loans.services import max_eligible_amount
from notifications.models import Notification


class LoanListView(generics.ListAPIView):
    serializer_class = LoanSerializer

    def get_queryset(self):
        return Loan.objects.filter(user=self.request.user).select_related('group')


class LoanEligibilityView(APIView):
    def get(self, request):
        return Response({'max_eligible_amount': max_eligible_amount(request.user)})


class RequestLoanView(generics.CreateAPIView):
    serializer_class = RequestLoanSerializer

    def create(self, request, *args, **kwargs):
        group_id = request.data.get('group_id')
        if not group_id:
            return Response(
                {'detail': 'A group is required to request a loan.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        unpaid_statuses = ['pending', 'active']

        same_group_unpaid = Loan.objects.filter(
            user=user, group_id=group_id, status__in=unpaid_statuses,
        ).exists()
        if same_group_unpaid:
            return Response(
                {'detail': 'You already have an unpaid loan in this group.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_unpaid = Loan.objects.filter(user=user, status__in=unpaid_statuses).count()
        if total_unpaid >= 2:
            return Response(
                {'detail': 'You already have 2 unpaid loans. Repay an existing loan before requesting another.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        loan = serializer.save()

        other_members = GroupMembership.objects.filter(
            group=loan.group,
        ).exclude(user=user).select_related('user')

        notifications = [
            Notification(
                user=membership.user,
                title='Loan request needs your vote',
                body=(
                    f'{user.full_name} requested a loan of {loan.amount:,.0f} CFA '
                    f'for "{loan.purpose}" in {loan.group.name}. Your vote is needed.'
                ),
                notification_type='loan_approval',
            )
            for membership in other_members
        ]
        if notifications:
            Notification.objects.bulk_create(notifications)

        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)


class LoanVoteView(APIView):
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk)
        user = request.user

        if loan.user_id == user.id:
            return Response({'detail': 'You cannot vote on this loan.'}, status=status.HTTP_403_FORBIDDEN)

        if not loan.group or not GroupMembership.objects.filter(group=loan.group, user=user).exists():
            return Response({'detail': 'You cannot vote on this loan.'}, status=status.HTTP_403_FORBIDDEN)

        if loan.status != 'pending':
            return Response({'detail': 'This loan is no longer pending.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VoteLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data['decision']

        LoanVote.objects.update_or_create(
            loan=loan, voter=user, defaults={'decision': decision},
        )

        approve_count = loan.votes.filter(decision='approve').count()
        reject_count = loan.votes.filter(decision='reject').count()
        eligible_voters = max(loan.group.member_count - 1, 0)
        majority = eligible_voters // 2 + 1

        if approve_count >= majority:
            loan.status = 'active'
            loan.approved_date = timezone.now().date()
            loan.remaining_balance = loan.amount
            loan.save(update_fields=['status', 'approved_date', 'remaining_balance'])

            loan.user.wallet_balance = loan.user.wallet_balance + loan.amount
            loan.user.save(update_fields=['wallet_balance'])

            record_transaction(
                user=loan.user,
                title=f'Loan disbursement - {loan.purpose}',
                amount=loan.amount,
                transaction_type='loan_disbursement',
                is_credit=True,
                group=loan.group,
            )

            Notification.objects.create(
                user=loan.user,
                title='Loan approved',
                body=(
                    f'Your loan request of {loan.amount:,.0f} CFA for "{loan.purpose}" '
                    f'has been approved by your group. The amount has been credited to your wallet.'
                ),
                notification_type='loan_approval',
            )
        elif reject_count >= majority:
            loan.status = 'rejected'
            loan.save(update_fields=['status'])

            Notification.objects.create(
                user=loan.user,
                title='Loan rejected',
                body=(
                    f'Your loan request of {loan.amount:,.0f} CFA for "{loan.purpose}" '
                    f'has been rejected by your group.'
                ),
                notification_type='loan_approval',
            )

        return Response({
            'loan_status': loan.status,
            'approve_count': approve_count,
            'reject_count': reject_count,
            'eligible_voters': eligible_voters,
            'majority_threshold': majority,
            'your_vote': decision,
        })


class PendingLoanVotesView(APIView):
    def get(self, request):
        user = request.user
        group_ids = GroupMembership.objects.filter(user=user).values_list('group_id', flat=True)

        loans = Loan.objects.filter(
            status='pending', group_id__in=group_ids,
        ).exclude(user=user).select_related('group', 'user')

        results = []
        for loan in loans:
            approve_count = loan.votes.filter(decision='approve').count()
            reject_count = loan.votes.filter(decision='reject').count()
            eligible_voters = max(loan.group.member_count - 1, 0)
            majority = eligible_voters // 2 + 1

            my_vote = loan.votes.filter(voter=user).first()

            results.append({
                'loan_id': loan.id,
                'requester_name': loan.user.full_name,
                'group_name': loan.group.name,
                'amount': loan.amount,
                'purpose': loan.purpose,
                'duration_months': loan.duration_months,
                'approve_count': approve_count,
                'reject_count': reject_count,
                'eligible_voters': eligible_voters,
                'majority_threshold': majority,
                'your_vote': my_vote.decision if my_vote else None,
            })

        return Response(results)


class LoanRepayView(APIView):
    def post(self, request, pk):
        loan = get_object_or_404(Loan, pk=pk, user=request.user)
        serializer = RepayLoanSerializer(
            data=request.data, context={'request': request, 'loan': loan},
        )
        serializer.is_valid(raise_exception=True)
        loan = serializer.save()
        return Response(LoanSerializer(loan).data)
