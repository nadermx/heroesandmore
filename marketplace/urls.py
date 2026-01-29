from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    # Listings
    path('', views.listing_list, name='listing_list'),
    path('create/', views.listing_create, name='listing_create'),
    path('<int:pk>/', views.listing_detail, name='listing_detail'),
    path('<int:pk>/edit/', views.listing_edit, name='listing_edit'),
    path('<int:pk>/publish/', views.listing_publish, name='listing_publish'),
    path('<int:pk>/cancel/', views.listing_cancel, name='listing_cancel'),
    path('<int:pk>/save/', views.save_listing, name='save_listing'),

    # Bidding and offers
    path('<int:pk>/bid/', views.place_bid, name='place_bid'),
    path('<int:pk>/offer/', views.make_offer, name='make_offer'),
    path('offer/<int:pk>/respond/', views.respond_offer, name='respond_offer'),

    # Checkout
    path('<int:pk>/checkout/', views.checkout, name='checkout'),
    path('order/<int:pk>/payment/', views.payment, name='payment'),

    # Orders
    path('order/<int:pk>/', views.order_detail, name='order_detail'),
    path('order/<int:pk>/ship/', views.order_ship, name='order_ship'),
    path('order/<int:pk>/received/', views.order_received, name='order_received'),
    path('order/<int:pk>/review/', views.leave_review, name='leave_review'),

    # User pages
    path('saved/', views.saved_listings, name='saved_listings'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('seller-setup/', views.seller_setup, name='seller_setup'),
]
