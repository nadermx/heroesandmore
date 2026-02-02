from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404

from pricing.models import PriceGuideItem, GradePrice, SaleRecord
from api.pagination import StandardResultsPagination
from .serializers import (
    PriceGuideItemListSerializer, PriceGuideItemDetailSerializer,
    GradePriceSerializer, SaleRecordSerializer, PriceHistorySerializer
)


class PriceGuideItemListView(generics.ListAPIView):
    """Browse price guide items"""
    serializer_class = PriceGuideItemListSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination
    search_fields = ['name', 'set_name', 'card_number']
    ordering_fields = ['name', 'year', 'total_sales', 'avg_sale_price']
    ordering = ['-total_sales']

    def get_queryset(self):
        queryset = PriceGuideItem.objects.select_related('category')

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        # Filter by year
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(year=year)

        # Filter by set
        set_name = self.request.query_params.get('set')
        if set_name:
            queryset = queryset.filter(set_name__icontains=set_name)

        return queryset


class PriceGuideItemDetailView(generics.RetrieveAPIView):
    """Get price guide item detail"""
    serializer_class = PriceGuideItemDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return PriceGuideItem.objects.select_related('category').prefetch_related('grade_prices')


class PriceGuideItemByIdView(generics.RetrieveAPIView):
    """Get price guide item by ID"""
    serializer_class = PriceGuideItemDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return PriceGuideItem.objects.select_related('category').prefetch_related('grade_prices')


class GradePricesView(generics.ListAPIView):
    """Get prices by grade for a price guide item"""
    serializer_class = GradePriceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        item_id = self.kwargs['pk']
        return GradePrice.objects.filter(price_guide_item_id=item_id).order_by('-grade')


class SaleRecordsView(generics.ListAPIView):
    """Get recent sales for a price guide item"""
    serializer_class = SaleRecordSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        item_id = self.kwargs['pk']
        return SaleRecord.objects.filter(
            price_guide_item_id=item_id
        ).order_by('-sale_date')


class PriceHistoryView(APIView):
    """Get price history for charts"""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        item = get_object_or_404(PriceGuideItem, pk=pk)

        # Get monthly aggregated data
        history = SaleRecord.objects.filter(
            price_guide_item=item
        ).annotate(
            month=TruncMonth('sale_date')
        ).values('month').annotate(
            avg_price=Avg('sale_price'),
            count=Count('id')
        ).order_by('month')

        data = [{
            'month': h['month'].isoformat() if h['month'] else None,
            'avg_price': float(h['avg_price']) if h['avg_price'] else 0,
            'count': h['count']
        } for h in history]

        return Response(data)


class TrendingItemsView(generics.ListAPIView):
    """Get trending items (most sales recently)"""
    serializer_class = PriceGuideItemListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return PriceGuideItem.objects.filter(
            total_sales__gt=0
        ).order_by('-total_sales', '-last_sale_date')[:20]


class PriceGuideSearchView(generics.ListAPIView):
    """Search price guide"""
    serializer_class = PriceGuideItemListSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        q = self.request.query_params.get('q', '')
        if not q:
            return PriceGuideItem.objects.none()

        return PriceGuideItem.objects.filter(
            name__icontains=q
        ).select_related('category').order_by('-total_sales')[:100]


class PriceGuideCategoriesView(APIView):
    """Get categories with price guide item counts"""
    permission_classes = [AllowAny]

    def get(self, request):
        from items.models import Category
        from django.db.models import Count

        categories = Category.objects.annotate(
            item_count=Count('price_guide_items')
        ).filter(item_count__gt=0).values(
            'id', 'name', 'slug', 'item_count'
        ).order_by('name')

        return Response(list(categories))
