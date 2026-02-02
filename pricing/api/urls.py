from django.urls import path
from . import views

app_name = 'pricing_api'

urlpatterns = [
    # Price guide items
    path('items/', views.PriceGuideItemListView.as_view(), name='item_list'),
    path('items/search/', views.PriceGuideSearchView.as_view(), name='search'),
    path('items/<int:pk>/', views.PriceGuideItemByIdView.as_view(), name='item_detail_by_id'),
    path('items/<slug:slug>/', views.PriceGuideItemDetailView.as_view(), name='item_detail'),
    path('items/<int:pk>/grades/', views.GradePricesView.as_view(), name='grades'),
    path('items/<int:pk>/sales/', views.SaleRecordsView.as_view(), name='sales'),
    path('items/<int:pk>/history/', views.PriceHistoryView.as_view(), name='history'),

    # Discovery
    path('trending/', views.TrendingItemsView.as_view(), name='trending'),
    path('categories/', views.PriceGuideCategoriesView.as_view(), name='categories'),
]
