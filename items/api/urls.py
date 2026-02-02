from django.urls import path
from . import views

app_name = 'items_api'

urlpatterns = [
    # Categories
    path('categories/', views.CategoryTreeView.as_view(), name='category_tree'),
    path('categories/list/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/<slug:slug>/listings/', views.CategoryListingsView.as_view(), name='category_listings'),

    # Search
    path('search/', views.GlobalSearchView.as_view(), name='search'),
    path('autocomplete/', views.AutocompleteView.as_view(), name='autocomplete'),
]
