from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from items.views import home
from accounts.api.views import (
    GoogleAuthView, PasswordResetView, PasswordResetConfirmView, ChangePasswordView
)
from app.views import log_frontend_error

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),

    # Frontend error logging
    path('api/log-error/', log_frontend_error, name='log_frontend_error'),

    # REST API v1
    path('api/v1/', include('api.urls')),

    # JWT Authentication
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/google/', GoogleAuthView.as_view(), name='google_auth'),
    path('api/v1/auth/password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('api/v1/auth/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('api/v1/auth/password/change/', ChangePasswordView.as_view(), name='password_change'),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('accounts/', include('accounts.urls')),
    path('auth/', include('allauth.urls')),
    path('collections/', include('user_collections.urls')),
    path('items/', include('items.urls')),
    path('marketplace/', include('marketplace.urls')),
    path('social/', include('social.urls')),
    path('alerts/', include('alerts.urls')),
    path('price-guide/', include('pricing.urls')),
    path('scanner/', include('scanner.urls')),
    path('seller/', include('seller_tools.urls')),

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
