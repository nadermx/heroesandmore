from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from affiliates.models import Affiliate, Referral, AffiliateCommission, AffiliatePayout
from api.pagination import StandardResultsPagination
from .serializers import (
    AffiliateSerializer, ReferralSerializer,
    AffiliateCommissionSerializer, AffiliatePayoutSerializer,
)


class AffiliateJoinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'affiliate'):
            serializer = AffiliateSerializer(request.user.affiliate)
            return Response(serializer.data)

        affiliate = Affiliate.objects.create(user=request.user)
        serializer = AffiliateSerializer(affiliate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AffiliateDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            affiliate = request.user.affiliate
        except Affiliate.DoesNotExist:
            return Response({'detail': 'Not an affiliate.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AffiliateSerializer(affiliate)
        return Response(serializer.data)


class AffiliateSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            affiliate = request.user.affiliate
        except Affiliate.DoesNotExist:
            return Response({'detail': 'Not an affiliate.'}, status=status.HTTP_404_NOT_FOUND)

        paypal_email = request.data.get('paypal_email', '').strip()
        if not paypal_email:
            return Response({'detail': 'PayPal email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        affiliate.paypal_email = paypal_email
        affiliate.save(update_fields=['paypal_email'])
        serializer = AffiliateSerializer(affiliate)
        return Response(serializer.data)


class ReferralListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReferralSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        try:
            affiliate = self.request.user.affiliate
        except Affiliate.DoesNotExist:
            return Referral.objects.none()
        return affiliate.referrals.select_related('referred_user').order_by('-created')


class CommissionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AffiliateCommissionSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        try:
            affiliate = self.request.user.affiliate
        except Affiliate.DoesNotExist:
            return AffiliateCommission.objects.none()
        qs = affiliate.commissions.order_by('-created')
        status_filter = self.request.query_params.get('status')
        if status_filter in ('pending', 'approved', 'paid', 'reversed'):
            qs = qs.filter(status=status_filter)
        return qs


class PayoutListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AffiliatePayoutSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        try:
            affiliate = self.request.user.affiliate
        except Affiliate.DoesNotExist:
            return AffiliatePayout.objects.none()
        return affiliate.payouts.order_by('-created')
