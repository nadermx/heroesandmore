import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

app = Celery('herosandmore')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    # Market data imports - runs at 6 AM and 6 PM daily
    'import-market-data-morning': {
        'task': 'pricing.tasks.import_all_market_data',
        'schedule': crontab(hour=6, minute=0),
    },
    'import-market-data-evening': {
        'task': 'pricing.tasks.import_all_market_data',
        'schedule': crontab(hour=18, minute=0),
    },
    # Check price alerts every hour
    'check-price-alerts': {
        'task': 'pricing.tasks.check_price_alerts',
        'schedule': crontab(minute=0),  # Every hour on the hour
    },
    # Update all price guide stats daily at 3 AM
    'update-price-guide-stats': {
        'task': 'pricing.tasks.update_all_price_guide_stats',
        'schedule': crontab(hour=3, minute=0),
    },
    # Subscription billing tasks
    'process-subscription-renewals': {
        'task': 'seller_tools.tasks.process_subscription_renewals',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'retry-failed-payments': {
        'task': 'seller_tools.tasks.retry_failed_payments',
        'schedule': crontab(minute=30),  # Every hour at :30
    },
    'expire-grace-periods': {
        'task': 'seller_tools.tasks.expire_grace_periods',
        'schedule': crontab(hour=3, minute=30),  # Daily at 3:30 AM
    },
    'send-renewal-reminders': {
        'task': 'seller_tools.tasks.send_renewal_reminders',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM
    },
}
