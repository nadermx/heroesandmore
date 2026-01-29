from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from items.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('auth/', include('allauth.urls')),
    path('collections/', include('user_collections.urls')),
    path('items/', include('items.urls')),
    path('marketplace/', include('marketplace.urls')),
    path('social/', include('social.urls')),
    path('alerts/', include('alerts.urls')),

    # Static pages
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    path('help/', TemplateView.as_view(template_name='pages/help.html'), name='help'),
    path('seller-guide/', TemplateView.as_view(template_name='pages/seller_guide.html'), name='seller_guide'),
    path('safety/', TemplateView.as_view(template_name='pages/safety.html'), name='safety'),
    path('contact/', TemplateView.as_view(template_name='pages/contact.html'), name='contact'),
    path('terms/', TemplateView.as_view(template_name='pages/terms.html'), name='terms'),
    path('privacy/', TemplateView.as_view(template_name='pages/privacy.html'), name='privacy'),
    path('cookies/', TemplateView.as_view(template_name='pages/cookies.html'), name='cookies'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
