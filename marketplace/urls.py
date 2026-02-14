from django.urls import path
from . import views
from . import webhooks

app_name = 'marketplace'

urlpatterns = [
    # Platform Auctions
    path('auctions/', views.platform_auctions, name='platform_auctions'),
    path('auctions/<slug:slug>/', views.platform_auction_detail, name='platform_auction_detail'),

    # Listings
    path('', views.listing_list, name='listing_list'),
    path('create/', views.listing_create, name='listing_create'),
    path('<int:pk>/', views.listing_detail, name='listing_detail'),
    path('<int:pk>/edit/', views.listing_edit, name='listing_edit'),
    path('<int:pk>/publish/', views.listing_publish, name='listing_publish'),
    path('<int:pk>/cancel/', views.listing_cancel, name='listing_cancel'),
    path('<int:pk>/relist/', views.listing_relist, name='listing_relist'),
    path('<int:pk>/save/', views.save_listing, name='save_listing'),

    # Bidding and offers
    path('<int:pk>/bid/', views.place_bid, name='place_bid'),
    path('<int:pk>/offer/', views.make_offer, name='make_offer'),
    path('offer/<int:pk>/respond/', views.respond_offer, name='respond_offer'),
    path('offer/<int:pk>/respond-counter/', views.respond_counter_offer, name='respond_counter_offer'),

    # Checkout
    path('<int:pk>/checkout/', views.checkout, name='checkout'),
    path('order/<int:pk>/payment/', views.payment, name='payment'),
    path('order/<int:pk>/complete/', views.checkout_complete, name='checkout_complete'),
    path('checkout/process/<int:pk>/', views.process_payment, name='process_payment'),

    # Payment methods
    path('payment-methods/', views.payment_methods, name='payment_methods'),
    path('payment-methods/add/', views.add_payment_method, name='add_payment_method'),

    # Orders
    path('order/<int:pk>/', views.order_detail, name='order_detail'),
    path('order/<int:pk>/ship/', views.order_ship, name='order_ship'),
    path('order/<int:pk>/received/', views.order_received, name='order_received'),
    path('order/<int:pk>/review/', views.leave_review, name='leave_review'),
    path('order/<int:pk>/refund/', views.order_refund, name='order_refund'),
    path('order/<int:pk>/cancel/', views.order_cancel, name='order_cancel'),

    # User pages
    path('saved/', views.saved_listings, name='saved_listings'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('my-orders/', views.my_orders, name='my_orders'),

    # Seller Setup (Stripe Connect)
    path('seller-setup/', views.seller_setup, name='seller_setup'),
    path('seller-setup/session/', views.seller_setup_session, name='seller_setup_session'),
    path('seller-setup/return/', views.seller_setup_return, name='seller_setup_return'),
    path('seller/stripe-dashboard/', views.seller_stripe_dashboard, name='seller_stripe_dashboard'),

    # Webhooks
    path('webhooks/stripe/', webhooks.stripe_webhook, name='stripe_webhook'),
    path('webhooks/stripe-connect/', webhooks.stripe_connect_webhook, name='stripe_connect_webhook'),
]
