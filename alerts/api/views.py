from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from alerts.models import Alert, Wishlist, WishlistItem, SavedSearch, PriceAlert
from api.pagination import StandardResultsPagination
from .serializers import (
    AlertSerializer, WishlistSerializer, WishlistCreateSerializer,
    WishlistItemSerializer, SavedSearchSerializer, SavedSearchCreateSerializer,
    PriceAlertSerializer, PriceAlertCreateSerializer
)


class AlertListView(generics.ListAPIView):
    """Get user's notifications"""
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user)


class AlertMarkReadView(APIView):
    """Mark alert as read"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk, user=request.user)
        alert.read = True
        alert.save()
        return Response({'status': 'marked as read'})


class AlertMarkAllReadView(APIView):
    """Mark all alerts as read"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Alert.objects.filter(user=request.user, read=False).update(read=True)
        return Response({'status': 'all marked as read'})


class WishlistViewSet(viewsets.ModelViewSet):
    """ViewSet for wishlists"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WishlistCreateSerializer
        return WishlistSerializer


class WishlistItemViewSet(viewsets.ModelViewSet):
    """ViewSet for wishlist items"""
    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        wishlist_id = self.kwargs.get('wishlist_pk')
        return WishlistItem.objects.filter(
            wishlist_id=wishlist_id,
            wishlist__user=self.request.user
        )

    def perform_create(self, serializer):
        wishlist_id = self.kwargs.get('wishlist_pk')
        wishlist = get_object_or_404(
            Wishlist, pk=wishlist_id, user=self.request.user
        )
        serializer.save(wishlist=wishlist)


class SavedSearchViewSet(viewsets.ModelViewSet):
    """ViewSet for saved searches"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedSearch.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SavedSearchCreateSerializer
        return SavedSearchSerializer

    @action(detail=True, methods=['get'])
    def matches(self, request, pk=None):
        """Get matching listings for this saved search"""
        saved_search = self.get_object()
        listings = saved_search.get_matching_listings()[:20]
        from marketplace.api.serializers import ListingListSerializer
        serializer = ListingListSerializer(listings, many=True, context={'request': request})
        return Response(serializer.data)


class PriceAlertViewSet(viewsets.ModelViewSet):
    """ViewSet for price alerts"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PriceAlert.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PriceAlertCreateSerializer
        return PriceAlertSerializer
