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
    # Expire unpaid orders every 5 minutes (releases reserved stock)
    'expire-unpaid-orders': {
        'task': 'marketplace.tasks.expire_unpaid_orders',
        'schedule': crontab(minute='*/5'),
    },
    # End auctions every 5 minutes
    'end-auctions': {
        'task': 'marketplace.tasks.end_auctions',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # Auto-activate platform auction events at bidding_start
    'activate-platform-events': {
        'task': 'marketplace.tasks.activate_platform_events',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # Send alert emails every 15 minutes
    'send-alert-emails': {
        'task': 'alerts.tasks.send_alert_emails',
        'schedule': crontab(minute='*/15'),
    },
    # Check wishlist matches daily
    'check-wishlist-matches': {
        'task': 'alerts.tasks.check_wishlist_matches',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    # Check ending auctions (notify bidders)
    'check-ending-auctions': {
        'task': 'alerts.tasks.check_ending_auctions',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    # Relist reminders for expired listings (3 days after expiry)
    'send-relist-reminders': {
        'task': 'alerts.tasks.send_relist_reminders',
        'schedule': crontab(hour=11, minute=0),  # Daily at 11 AM
    },
    # Update trusted seller status daily
    'update-trusted-seller-status': {
        'task': 'seller_tools.tasks.update_trusted_seller_status',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
    },
    # Weekly auction digest (Friday 10 AM)
    'weekly-auction-digest': {
        'task': 'alerts.tasks.send_weekly_auction_digest',
        'schedule': crontab(hour=10, minute=0, day_of_week=5),  # Friday
    },
    # Watched auction final 24h alerts (every 30 minutes)
    'watched-auction-final-24h': {
        'task': 'alerts.tasks.send_watched_auction_final_24h',
        'schedule': crontab(minute='*/30'),
    },
    # Weekly results recap (Monday 10 AM)
    'weekly-results-recap': {
        'task': 'alerts.tasks.send_weekly_results_recap',
        'schedule': crontab(hour=10, minute=0, day_of_week=1),  # Monday
    },
    # Cleanup expired shipping rate quotes (daily at 1 AM)
    'cleanup-expired-shipping-rates': {
        'task': 'shipping.tasks.cleanup_expired_rates',
        'schedule': crontab(hour=1, minute=0),
    },
    # Poll USPS tracking for shipped orders (every 2 hours)
    'poll-usps-tracking': {
        'task': 'shipping.tasks.poll_usps_tracking',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    # Expire stale guest listing submissions (daily at 2:30 AM)
    'cleanup-guest-submissions': {
        'task': 'marketplace.tasks.cleanup_expired_guest_submissions',
        'schedule': crontab(hour=2, minute=30),
    },
    # Approve affiliate commissions older than 30 days (daily at 5 AM)
    'approve-affiliate-commissions': {
        'task': 'affiliates.tasks.approve_pending_commissions',
        'schedule': crontab(hour=5, minute=0),
    },
    # Process affiliate payouts (1st of month at 5:30 AM)
    'process-affiliate-payouts': {
        'task': 'affiliates.tasks.process_affiliate_payouts',
        'schedule': crontab(hour=5, minute=30, day_of_month=1),
    },
    # Review follow-up reminders (3 days after delivery, daily at 9 AM)
    'review-followup-reminders': {
        'task': 'alerts.tasks.send_review_followup_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
    # Seller delivery follow-up (1 day after delivery, daily at 9:30 AM)
    'seller-delivery-followup': {
        'task': 'alerts.tasks.send_seller_delivery_followup',
        'schedule': crontab(hour=9, minute=30),
    },
    # New listings digest (Wednesday 10 AM)
    'new-listings-digest': {
        'task': 'alerts.tasks.send_new_listings_digest',
        'schedule': crontab(hour=10, minute=0, day_of_week=3),
    },
    # Post-purchase follow-up (daily at 10:30 AM)
    'post-purchase-followup': {
        'task': 'alerts.tasks.send_post_purchase_followup',
        'schedule': crontab(hour=10, minute=30),
    },
}
