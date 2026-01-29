from django.urls import path
from . import views

app_name = 'seller_tools'

urlpatterns = [
    # Dashboard
    path('', views.seller_dashboard, name='dashboard'),

    # Subscription management
    path('subscription/', views.subscription_manage, name='subscription'),
    path('subscription/upgrade/<str:tier>/', views.subscription_upgrade, name='subscription_upgrade'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),

    # Bulk import
    path('import/', views.bulk_import_list, name='import_list'),
    path('import/new/', views.bulk_import_create, name='import_create'),
    path('import/<int:pk>/', views.bulk_import_detail, name='import_detail'),
    path('import/<int:pk>/process/', views.bulk_import_process, name='import_process'),
    path('import/template/', views.download_import_template, name='import_template'),

    # Inventory management
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/add/', views.inventory_add, name='inventory_add'),
    path('inventory/<int:pk>/', views.inventory_detail, name='inventory_detail'),
    path('inventory/<int:pk>/edit/', views.inventory_edit, name='inventory_edit'),
    path('inventory/<int:pk>/create-listing/', views.inventory_create_listing, name='inventory_create_listing'),

    # Analytics
    path('analytics/', views.seller_analytics, name='analytics'),
    path('analytics/sales/', views.sales_report, name='sales_report'),
    path('analytics/export/', views.export_analytics, name='export_analytics'),
]
