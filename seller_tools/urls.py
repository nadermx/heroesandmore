from django.urls import path
from . import views

app_name = 'seller_tools'

urlpatterns = [
    # Dashboard
    path('', views.seller_dashboard, name='dashboard'),

    # Subscription management
    path('subscription/', views.subscription_manage, name='subscription'),
    path('subscription/upgrade/<str:tier>/', views.subscription_upgrade, name='subscription_upgrade'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('subscription/reactivate/', views.subscription_reactivate, name='subscription_reactivate'),
    path('subscription/payment-methods/', views.subscription_payment_methods, name='subscription_payment_methods'),
    path('subscription/billing-history/', views.subscription_billing_history, name='subscription_billing_history'),

    # Payout settings
    path('payouts/', views.payout_settings, name='payout_settings'),

    # Ship-from address
    path('ship-from/', views.ship_from_address, name='ship_from_address'),

    # Bulk import
    path('import/', views.bulk_import_list, name='import_list'),
    path('import/new/', views.bulk_import_create, name='import_create'),
    path('import/<int:pk>/', views.bulk_import_detail, name='import_detail'),
    path('import/<int:pk>/process/', views.bulk_import_process, name='import_process'),
    path('import/template/', views.download_import_template, name='import_template'),

    # Import photo capture flow
    path('import/<int:pk>/photos/', views.import_photos, name='import_photos'),
    path('import/<int:pk>/photos/<int:listing_id>/', views.import_photo_capture, name='import_photo_capture'),
    path('import/<int:pk>/photos/<int:listing_id>/upload/', views.import_photo_upload, name='import_photo_upload'),
    path('import/<int:pk>/photos/<int:listing_id>/delete/<int:position>/', views.import_photo_delete, name='import_photo_delete'),

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
