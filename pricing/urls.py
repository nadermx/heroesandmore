from django.urls import path
from . import views

app_name = 'pricing'

urlpatterns = [
    # Price guide browsing
    path('', views.PriceGuideListView.as_view(), name='price_guide_list'),
    path('category/<slug:category_slug>/', views.PriceGuideListView.as_view(), name='price_guide_category'),
    path('item/<slug:slug>/', views.PriceGuideDetailView.as_view(), name='price_guide_detail'),

    # Search and API
    path('search/', views.price_guide_search, name='price_guide_search'),
    path('api/suggest/', views.get_price_suggestion, name='get_price_suggestion'),
    path('api/history/<int:item_id>/', views.get_price_history, name='get_price_history'),

    # Trending and popular
    path('trending/', views.trending_items, name='trending'),
    path('popular/', views.popular_items, name='popular'),
]
