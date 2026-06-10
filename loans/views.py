from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from loans.models import Loan
from loans.serializers import LoanSerializer, RequestLoanSerializer


class LoanListView(generics.ListAPIView):
    serializer_class = LoanSerializer

    def get_queryset(self):
        return Loan.objects.filter(user=self.request.user).select_related('group')


class LoanEligibilityView(APIView):
    def get(self, request):
        mri = float(request.user.mri_score)
        if mri >= 9.0:
            max_amount = 500000
        elif mri >= 8.0:
            max_amount = 350000
        elif mri >= 7.0:
            max_amount = 200000
        else:
            max_amount = 100000
        return Response({'max_eligible_amount': max_amount})


class RequestLoanView(generics.CreateAPIView):
    serializer_class = RequestLoanSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = serializer.save()
        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)
