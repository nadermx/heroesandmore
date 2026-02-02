from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.db.models import Q

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

        # For other actions, filter by ownership
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
