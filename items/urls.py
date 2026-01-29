from django.urls import path
from . import views

app_name = 'items'

urlpatterns = [
    path('', views.category_list, name='category_list'),
    path('search/', views.search, name='search'),
    path('<slug:slug>/', views.category_detail, name='category'),
    path('<slug:category_slug>/<slug:slug>/', views.item_detail, name='item_detail'),
]
