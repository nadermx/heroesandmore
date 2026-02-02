from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db.models import Q
import csv
import json
from io import StringIO
from decimal import Decimal

from user_collections.models import Collection, CollectionItem, CollectionValueSnapshot
from api.permissions import IsOwnerOrReadOnly
from .serializers import (
    CollectionSerializer, CollectionCreateSerializer,
    CollectionItemSerializer, CollectionItemCreateSerializer,
    CollectionValueSnapshotSerializer
)


class CollectionViewSet(viewsets.ModelViewSet):
    """ViewSet for collections"""
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if self.action == 'list':
            if user.is_authenticated:
                # Show own collections + public collections
                return Collection.objects.filter(
                    Q(user=user) | Q(is_public=True)
                ).distinct()
            return Collection.objects.filter(is_public=True)

        # For retrieve/value/value_history, allow access to public collections or own
        if self.action in ['retrieve', 'value', 'value_history', 'items']:
            if user.is_authenticated:
                return Collection.objects.filter(
                    Q(user=user) | Q(is_public=True)
                ).distinct()
            return Collection.objects.filter(is_public=True)

        # For export and other write actions, filter by ownership only
        if user.is_authenticated:
            return Collection.objects.filter(user=user)
        return Collection.objects.none()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CollectionCreateSerializer
        return CollectionSerializer

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """Get only the current user's collections"""
        if not request.user.is_authenticated:
            return Response([], status=status.HTTP_200_OK)
        collections = Collection.objects.filter(user=request.user)
        serializer = CollectionSerializer(collections, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get items in a collection"""
        collection = self.get_object()
        # Check permission for private collections
        if not collection.is_public and collection.user != request.user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        items = collection.items.all()
        serializer = CollectionItemSerializer(items, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def value(self, request, pk=None):
        """Get collection value summary"""
        collection = self.get_object()
        if not collection.is_public and collection.user != request.user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({
            'total_value': str(collection.total_value or collection.get_total_value()),
            'total_cost': str(collection.total_cost or collection.get_total_cost()),
            'item_count': collection.item_count(),
            'gain_loss': str((collection.total_value or 0) - (collection.total_cost or 0))
        })

    @action(detail=True, methods=['get'])
    def value_history(self, request, pk=None):
        """Get collection value history for charts"""
        collection = self.get_object()
        if not collection.is_public and collection.user != request.user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        snapshots = collection.value_snapshots.all()[:90]  # Last 90 days
        serializer = CollectionValueSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export collection as CSV or JSON"""
        collection = self.get_object()
        if collection.user != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        export_format = request.query_params.get('export_format', request.query_params.get('format', 'csv'))
        items = collection.items.all()

        if export_format == 'json':
            data = {
                'collection': {
                    'name': collection.name,
                    'description': collection.description,
                },
                'items': [
                    {
                        'name': item.get_name(),
                        'category': item.category.name if item.category else '',
                        'condition': item.condition or '',
                        'grading_company': item.grading_company or '',
                        'grade': item.grade or '',
                        'cert_number': item.cert_number or '',
                        'purchase_price': str(item.purchase_price) if item.purchase_price else '',
                        'purchase_date': item.purchase_date.isoformat() if item.purchase_date else '',
                        'current_value': str(item.current_value) if item.current_value else '',
                        'notes': item.notes or '',
                    }
                    for item in items
                ]
            }
            response = HttpResponse(
                json.dumps(data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="{collection.name}.json"'
            return response
        else:
            # CSV export
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Name', 'Category', 'Condition', 'Grading Company', 'Grade',
                'Cert Number', 'Purchase Price', 'Purchase Date', 'Current Value', 'Notes'
            ])
            for item in items:
                writer.writerow([
                    item.get_name(),
                    item.category.name if item.category else '',
                    item.condition or '',
                    item.grading_company or '',
                    item.grade or '',
                    item.cert_number or '',
                    str(item.purchase_price) if item.purchase_price else '',
                    item.purchase_date.isoformat() if item.purchase_date else '',
                    str(item.current_value) if item.current_value else '',
                    item.notes or '',
                ])

            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{collection.name}.csv"'
            return response


class CollectionImportView(generics.CreateAPIView):
    """Import collection from CSV or JSON file"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        file = request.FILES['file']
        file_name = file.name.lower()

        # Determine format
        if file_name.endswith('.json'):
            return self._import_json(request, file)
        elif file_name.endswith('.csv'):
            return self._import_csv(request, file)
        else:
            return Response(
                {'error': 'File must be .csv or .json'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _import_json(self, request, file):
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return Response(
                {'error': 'Invalid JSON file'},
                status=status.HTTP_400_BAD_REQUEST
            )

        collection_data = data.get('collection', {})
        items_data = data.get('items', [])

        # Create collection
        collection = Collection.objects.create(
            user=request.user,
            name=collection_data.get('name', 'Imported Collection'),
            description=collection_data.get('description', ''),
        )

        # Create items
        created_count = 0
        for item_data in items_data:
            try:
                CollectionItem.objects.create(
                    collection=collection,
                    name=item_data.get('name', ''),
                    condition=item_data.get('condition', ''),
                    grading_company=item_data.get('grading_company', ''),
                    grade=item_data.get('grade', ''),
                    cert_number=item_data.get('cert_number', ''),
                    purchase_price=Decimal(item_data['purchase_price']) if item_data.get('purchase_price') else None,
                    current_value=Decimal(item_data['current_value']) if item_data.get('current_value') else None,
                    notes=item_data.get('notes', ''),
                )
                created_count += 1
            except (ValueError, KeyError):
                continue

        return Response({
            'collection_id': collection.id,
            'collection_name': collection.name,
            'items_imported': created_count,
            'items_total': len(items_data),
        }, status=status.HTTP_201_CREATED)

    def _import_csv(self, request, file):
        try:
            content = file.read().decode('utf-8')
            reader = csv.DictReader(StringIO(content))
            rows = list(reader)
        except Exception as e:
            return Response(
                {'error': f'Error reading CSV: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        collection_name = request.data.get('name', 'Imported Collection')

        # Create collection
        collection = Collection.objects.create(
            user=request.user,
            name=collection_name,
            description=request.data.get('description', ''),
        )

        # Create items
        created_count = 0
        for row in rows:
            try:
                CollectionItem.objects.create(
                    collection=collection,
                    name=row.get('Name', row.get('name', '')),
                    condition=row.get('Condition', row.get('condition', '')),
                    grading_company=row.get('Grading Company', row.get('grading_company', '')),
                    grade=row.get('Grade', row.get('grade', '')),
                    cert_number=row.get('Cert Number', row.get('cert_number', '')),
                    purchase_price=Decimal(row['Purchase Price']) if row.get('Purchase Price') else None,
                    current_value=Decimal(row['Current Value']) if row.get('Current Value') else None,
                    notes=row.get('Notes', row.get('notes', '')),
                )
                created_count += 1
            except (ValueError, KeyError, Exception):
                continue

        return Response({
            'collection_id': collection.id,
            'collection_name': collection.name,
            'items_imported': created_count,
            'items_total': len(rows),
        }, status=status.HTTP_201_CREATED)


class CollectionItemViewSet(viewsets.ModelViewSet):
    """ViewSet for collection items"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        collection_id = self.kwargs.get('collection_pk')
        return CollectionItem.objects.filter(
            collection_id=collection_id,
            collection__user=self.request.user
        )

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CollectionItemCreateSerializer
        return CollectionItemSerializer

    def perform_create(self, serializer):
        collection_id = self.kwargs.get('collection_pk')
        collection = get_object_or_404(
            Collection, pk=collection_id, user=self.request.user
        )
        serializer.save(collection=collection)


class PublicCollectionsView(generics.ListAPIView):
    """Browse public collections"""
    serializer_class = CollectionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Collection.objects.filter(is_public=True).order_by('-updated')
