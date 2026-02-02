from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'alerts_api'

router = DefaultRouter()
router.register('wishlists', views.WishlistViewSet, basename='wishlist')
router.register('saved-searches', views.SavedSearchViewSet, basename='saved-search')
router.register('price-alerts', views.PriceAlertViewSet, basename='price-alert')

urlpatterns = [
    path('', include(router.urls)),

    # Notifications
    path('notifications/', views.AlertListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.AlertMarkReadView.as_view(), name='mark_read'),
    path('notifications/read-all/', views.AlertMarkAllReadView.as_view(), name='mark_all_read'),

    # Wishlist items
    path('wishlists/<int:wishlist_pk>/items/', views.WishlistItemViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='wishlist-items'),
    path('wishlists/<int:wishlist_pk>/items/<int:pk>/', views.WishlistItemViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='wishlist-item-detail'),
]
