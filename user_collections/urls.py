from django.urls import path
from . import views

app_name = 'collections'

urlpatterns = [
    path('', views.collection_list, name='collection_list'),
    path('my/', views.my_collections, name='my_collections'),
    path('create/', views.collection_create, name='collection_create'),
    path('<int:pk>/', views.collection_detail, name='collection_detail'),
    path('<int:pk>/edit/', views.collection_edit, name='collection_edit'),
    path('<int:pk>/delete/', views.collection_delete, name='collection_delete'),
    path('<int:pk>/export/', views.collection_export, name='collection_export'),
    path('<int:pk>/import/', views.collection_import, name='collection_import'),
    path('<int:pk>/add-item/', views.item_add, name='item_add'),
    path('item/<int:pk>/edit/', views.item_edit, name='item_edit'),
    path('item/<int:pk>/delete/', views.item_delete, name='item_delete'),
    path('add-listing/<int:listing_pk>/', views.add_listing_to_collection, name='add_listing'),
    path('user/<str:username>/', views.collection_list, name='user_collections'),
]
