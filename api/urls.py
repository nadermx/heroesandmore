from django.urls import path, include

app_name = 'api'

urlpatterns = [
    path('accounts/', include('accounts.api.urls')),
    path('marketplace/', include('marketplace.api.urls')),
    path('collections/', include('user_collections.api.urls')),
    path('pricing/', include('pricing.api.urls')),
    path('alerts/', include('alerts.api.urls')),
    path('social/', include('social.api.urls')),
    path('scanner/', include('scanner.api.urls')),
    path('seller/', include('seller_tools.api.urls')),
    path('items/', include('items.api.urls')),
]
