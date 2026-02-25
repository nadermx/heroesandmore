from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('addresses', views.AddressViewSet, basename='address')
router.register('profiles', views.ShippingProfileViewSet, basename='shipping-profile')

urlpatterns = [
    path('', include(router.urls)),
    path('addresses/validate/', views.validate_address, name='validate-address'),
    path('rates/', views.get_rates, name='get-rates'),
    path('labels/<int:order_id>/buy/', views.buy_label, name='buy-label'),
    path('labels/<int:order_id>/', views.label_detail, name='label-detail'),
    path('labels/<int:order_id>/void/', views.void_label, name='void-label'),
    path('tracking/<int:order_id>/', views.tracking_info, name='tracking-info'),
]
