from django.urls import path
from . import views

app_name = 'scanner'

urlpatterns = [
    # Scanner interface
    path('', views.scanner_home, name='home'),
    path('upload/', views.upload_scan, name='upload'),
    path('result/<int:pk>/', views.scan_result, name='result'),

    # Bulk scanning
    path('session/', views.scan_session, name='session'),
    path('session/<int:pk>/', views.session_detail, name='session_detail'),

    # Actions from scan results
    path('result/<int:pk>/create-listing/', views.create_listing_from_scan, name='create_listing'),
    path('result/<int:pk>/add-to-collection/', views.add_to_collection_from_scan, name='add_to_collection'),

    # API endpoints
    path('api/scan/', views.api_scan, name='api_scan'),
    path('api/status/<int:pk>/', views.api_scan_status, name='api_status'),
]
