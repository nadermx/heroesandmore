from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'marketplace_api'

router = DefaultRouter()
router.register('listings', views.ListingViewSet, basename='listing')
router.register('offers', views.OfferViewSet, basename='offer')
router.register('orders', views.OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),

    # Saved listings
    path('saved/', views.SavedListingsView.as_view(), name='saved_listings'),

    # Auction events
    path('auctions/events/', views.AuctionEventListView.as_view(), name='auction_events'),
    path('auctions/events/<slug:slug>/', views.AuctionEventDetailView.as_view(), name='auction_event_detail'),
    path('auctions/events/<slug:slug>/lots/', views.AuctionEventLotsView.as_view(), name='auction_event_lots'),
    path('auctions/ending-soon/', views.EndingSoonView.as_view(), name='ending_soon'),
]
