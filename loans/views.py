from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from loans.models import Loan
from loans.serializers import LoanSerializer, RequestLoanSerializer
from loans.services import max_eligible_amount


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
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        loan = serializer.save()
        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)
