from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'scanner_api'

router = DefaultRouter()
router.register('sessions', views.ScanSessionViewSet, basename='session')

urlpatterns = [
    path('', include(router.urls)),

    # Single scans
    path('scan/', views.ScanUploadView.as_view(), name='upload'),
    path('scan/<int:pk>/', views.ScanResultDetailView.as_view(), name='detail'),
    path('scan/<int:pk>/create-listing/', views.CreateListingFromScanView.as_view(), name='create_listing'),
    path('scan/<int:pk>/add-to-collection/', views.AddToCollectionFromScanView.as_view(), name='add_to_collection'),
    path('scans/', views.ScanHistoryView.as_view(), name='history'),
]
