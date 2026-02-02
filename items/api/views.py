from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db.models import Q

from items.models import Category, Item
from marketplace.models import Listing
from pricing.models import PriceGuideItem
from api.pagination import StandardResultsPagination
from .serializers import (
    CategorySerializer, CategoryListSerializer, ItemSerializer,
    SearchResultSerializer, AutocompleteSerializer
)


class CategoryTreeView(generics.ListAPIView):
    """Get all categories as a tree"""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # Only return top-level categories (children are nested)
        return Category.objects.filter(
            parent__isnull=True,
            is_active=True
        ).prefetch_related('children')


class CategoryListView(generics.ListAPIView):
    """Get flat list of all categories"""
    serializer_class = CategoryListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Category.objects.filter(is_active=True)


class CategoryDetailView(generics.RetrieveAPIView):
    """Get category detail"""
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Category.objects.filter(is_active=True)


class CategoryListingsView(generics.ListAPIView):
    """Get listings in a category"""
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        slug = self.kwargs['slug']
        category = Category.objects.filter(slug=slug).first()
        if not category:
            return Listing.objects.none()

        # Include subcategories
        category_ids = [category.id]
        for child in category.get_descendants():
            category_ids.append(child.id)

        return Listing.objects.filter(
            category_id__in=category_ids,
            status='active'
        ).select_related('seller', 'category')

    def get_serializer_class(self):
        from marketplace.api.serializers import ListingListSerializer
        return ListingListSerializer


class GlobalSearchView(APIView):
    """Global search across listings, items, and price guide"""
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q or len(q) < 2:
            return Response([])

        results = []
        limit = 10

        # Search listings
        listings = Listing.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q),
            status='active'
        ).select_related('category')[:limit]

        for listing in listings:
            results.append({
                'type': 'listing',
                'id': listing.id,
                'title': listing.title,
                'price': str(listing.price),
                'image_url': request.build_absolute_uri(listing.image1.url) if listing.image1 else None,
                'url': listing.get_absolute_url()
            })

        # Search price guide
        price_items = PriceGuideItem.objects.filter(
            name__icontains=q
        )[:limit]

        for item in price_items:
            results.append({
                'type': 'price_guide',
                'id': item.id,
                'title': item.name,
                'price': str(item.avg_sale_price) if item.avg_sale_price else None,
                'image_url': request.build_absolute_uri(item.image.url) if item.image else None,
                'url': item.get_absolute_url()
            })

        return Response(results[:20])


class AutocompleteView(APIView):
    """Autocomplete suggestions for search"""
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q or len(q) < 2:
            return Response([])

        suggestions = []
        limit = 8

        # Listing titles
        listings = Listing.objects.filter(
            title__icontains=q,
            status='active'
        ).values_list('title', flat=True).distinct()[:limit]

        for title in listings:
            suggestions.append({
                'text': title,
                'type': 'listing',
                'url': f'/marketplace/?q={title}'
            })

        # Price guide items
        price_items = PriceGuideItem.objects.filter(
            name__icontains=q
        ).values('name', 'slug')[:limit]

        for item in price_items:
            suggestions.append({
                'text': item['name'],
                'type': 'price_guide',
                'url': f'/price-guide/item/{item["slug"]}/'
            })

        # Categories
        categories = Category.objects.filter(
            name__icontains=q,
            is_active=True
        ).values('name', 'slug')[:4]

        for cat in categories:
            suggestions.append({
                'text': cat['name'],
                'type': 'category',
                'url': f'/items/category/{cat["slug"]}/'
            })

        return Response(suggestions[:12])
