from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'seller_api'

router = DefaultRouter()
router.register('inventory', views.InventoryViewSet, basename='inventory')
router.register('imports', views.BulkImportViewSet, basename='import')

urlpatterns = [
    path('', include(router.urls)),

    # Dashboard and analytics
    path('dashboard/', views.SellerDashboardView.as_view(), name='dashboard'),
    path('analytics/', views.SellerAnalyticsView.as_view(), name='analytics'),

    # Subscription
    path('subscription/', views.SubscriptionView.as_view(), name='subscription'),
    path('subscription/upgrade/', views.SubscriptionUpgradeView.as_view(), name='subscription_upgrade'),
    path('subscription/cancel/', views.SubscriptionCancelView.as_view(), name='subscription_cancel'),
    path('subscription/reactivate/', views.SubscriptionReactivateView.as_view(), name='subscription_reactivate'),
    path('billing-history/', views.BillingHistoryView.as_view(), name='billing_history'),

    # Orders
    path('orders/', views.SellerOrdersView.as_view(), name='orders'),
    path('sales/', views.SellerSalesHistoryView.as_view(), name='sales'),
]
