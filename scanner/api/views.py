from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from scanner.models import ScanResult, ScanSession
from api.pagination import StandardResultsPagination
from .serializers import (
    ScanResultSerializer, ScanUploadSerializer,
    ScanSessionSerializer, ScanSessionCreateSerializer,
    CreateFromScanSerializer
)


class ScanUploadView(APIView):
    """Upload image for scanning"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ScanUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create scan result
        scan = ScanResult.objects.create(
            user=request.user,
            image=serializer.validated_data['image'],
            status='pending'
        )

        # TODO: Trigger async task for image recognition
        # from scanner.tasks import process_scan
        # process_scan.delay(scan.id)

        return Response(
            ScanResultSerializer(scan, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ScanResultDetailView(generics.RetrieveAPIView):
    """Get scan result detail"""
    serializer_class = ScanResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ScanResult.objects.filter(user=self.request.user)


class ScanHistoryView(generics.ListAPIView):
    """Get user's scan history"""
    serializer_class = ScanResultSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return ScanResult.objects.filter(user=self.request.user)


class CreateListingFromScanView(APIView):
    """Create a listing from scan result"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        scan = get_object_or_404(ScanResult, pk=pk, user=request.user)

        if scan.converted_to_listing:
            return Response(
                {'error': 'Scan already converted to listing'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CreateFromScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from marketplace.models import Listing
        from items.models import Category

        # Get category
        category_id = serializer.validated_data.get('category')
        if not category_id and scan.extracted_data.get('category'):
            # Try to find category from extracted data
            pass

        category = get_object_or_404(Category, pk=category_id) if category_id else None
        if not category:
            return Response(
                {'error': 'Category is required to create a listing'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create listing
        listing = Listing.objects.create(
            seller=request.user,
            title=serializer.validated_data.get('title') or scan.get_suggested_title(),
            price=serializer.validated_data.get('price', 0),
            category=category,
            image1=scan.image,
            description='',
            condition='good',
            status='draft',
            price_guide_item=scan.identified_item
        )

        # Update scan
        scan.converted_to_listing = listing
        scan.save()

        from marketplace.api.serializers import ListingDetailSerializer
        return Response(
            ListingDetailSerializer(listing, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class AddToCollectionFromScanView(APIView):
    """Add scan result to collection"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        scan = get_object_or_404(ScanResult, pk=pk, user=request.user)

        if scan.added_to_collection:
            return Response(
                {'error': 'Scan already added to collection'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CreateFromScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from user_collections.models import Collection, CollectionItem

        collection_id = serializer.validated_data.get('collection_id')
        collection = get_object_or_404(
            Collection, pk=collection_id, user=request.user
        )

        # Create collection item
        item = CollectionItem.objects.create(
            collection=collection,
            name=scan.get_suggested_title(),
            image=scan.image,
            price_guide_item=scan.identified_item,
            purchase_price=serializer.validated_data.get('purchase_price'),
            condition=scan.extracted_data.get('condition', '')
        )

        # Update scan
        scan.added_to_collection = item
        scan.save()

        from user_collections.api.serializers import CollectionItemSerializer
        return Response(
            CollectionItemSerializer(item, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ScanSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for scan sessions"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return ScanSession.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return ScanSessionCreateSerializer
        return ScanSessionSerializer

    def perform_create(self, serializer):
        ScanSession.objects.create(
            user=self.request.user,
            name=serializer.validated_data.get('name', '')
        )

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def scan(self, request, pk=None):
        """Add a scan to this session"""
        session = self.get_object()

        upload_serializer = ScanUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        scan = ScanResult.objects.create(
            user=request.user,
            image=upload_serializer.validated_data['image'],
            status='pending'
        )

        # Update session counts
        session.total_scans += 1
        session.save()

        # TODO: Trigger async processing

        return Response(
            ScanResultSerializer(scan, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
