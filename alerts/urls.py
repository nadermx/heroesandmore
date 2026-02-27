from django.urls import path
from . import views

app_name = 'alerts'

urlpatterns = [
    # Alerts/Notifications
    path('', views.alerts_list, name='alerts_list'),
    path('unread-count/', views.unread_count, name='unread_count'),
    path('<int:pk>/read/', views.mark_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('<int:pk>/delete/', views.delete_alert, name='delete_alert'),

    # Wishlists
    path('wishlists/', views.wishlist_list, name='wishlist_list'),
    path('wishlists/create/', views.wishlist_create, name='wishlist_create'),
    path('wishlists/<int:pk>/', views.wishlist_detail, name='wishlist_detail'),
    path('wishlists/<int:pk>/edit/', views.wishlist_edit, name='wishlist_edit'),
    path('wishlists/<int:pk>/delete/', views.wishlist_delete, name='wishlist_delete'),
    path('wishlists/<int:pk>/add-item/', views.wishlist_item_add, name='wishlist_item_add'),
    path('wishlist-item/<int:pk>/edit/', views.wishlist_item_edit, name='wishlist_item_edit'),
    path('wishlist-item/<int:pk>/delete/', views.wishlist_item_delete, name='wishlist_item_delete'),

    # Saved Searches
    path('searches/', views.saved_search_list, name='saved_search_list'),
    path('searches/save/', views.saved_search_create, name='saved_search_create'),
    path('searches/<int:pk>/delete/', views.saved_search_delete, name='saved_search_delete'),
]
