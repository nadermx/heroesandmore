from django.urls import path
from . import webhooks

app_name = 'shipping'

urlpatterns = [
    path('webhooks/easypost/', webhooks.easypost_webhook, name='easypost_webhook'),
]
