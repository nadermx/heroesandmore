from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers
from . import views

app_name = 'collections_api'

# Main router
router = DefaultRouter()
router.register('', views.CollectionViewSet, basename='collection')

# Nested router for collection items
# Note: If rest_framework_nested is not installed, use simple URLs instead
try:
    collections_router = nested_routers.NestedDefaultRouter(router, '', lookup='collection')
    collections_router.register('items', views.CollectionItemViewSet, basename='collection-items')
    nested_urls = collections_router.urls
except ImportError:
    nested_urls = []

urlpatterns = [
    # Explicit paths must come before router to take precedence
    path('public/', views.PublicCollectionsView.as_view(), name='public_collections'),
    path('import/', views.CollectionImportView.as_view(), name='collection_import'),
    # Router-based routes
    path('', include(router.urls)),
]

# Add nested routes if available
urlpatterns += nested_urls

# Fallback simple item routes if nested router not available
if not nested_urls:
    urlpatterns += [
        path('<int:collection_pk>/items/', views.CollectionItemViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='collection-items-list'),
        path('<int:collection_pk>/items/<int:pk>/', views.CollectionItemViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='collection-items-detail'),
    ]
