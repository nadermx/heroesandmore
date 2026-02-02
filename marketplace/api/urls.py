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

    # Listing images
    path('listings/<int:pk>/images/', views.ListingImageUploadView.as_view(), name='listing_image_upload'),
    path('listings/<int:pk>/images/<int:image_id>/', views.ListingImageDeleteView.as_view(), name='listing_image_delete'),

    # Checkout and payment
    path('checkout/<int:pk>/', views.CheckoutView.as_view(), name='checkout'),
    path('payment/intent/', views.PaymentIntentView.as_view(), name='payment_intent'),
    path('payment/confirm/', views.PaymentConfirmView.as_view(), name='payment_confirm'),

    # Auction events
    path('auctions/events/', views.AuctionEventListView.as_view(), name='auction_events'),
    path('auctions/events/<slug:slug>/', views.AuctionEventDetailView.as_view(), name='auction_event_detail'),
    path('auctions/events/<slug:slug>/lots/', views.AuctionEventLotsView.as_view(), name='auction_event_lots'),
    path('auctions/ending-soon/', views.EndingSoonView.as_view(), name='ending_soon'),

    # Auto-bid
    path('auctions/autobid/', views.AutoBidListView.as_view(), name='autobid_list'),
    path('auctions/autobid/<int:pk>/', views.AutoBidDeleteView.as_view(), name='autobid_delete'),
]
