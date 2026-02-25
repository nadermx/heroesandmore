import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('shipping')


@shared_task
def cleanup_expired_rates():
    """Delete expired shipping rate quotes (older than cache window)."""
    from shipping.models import ShippingRate

    expired = ShippingRate.objects.filter(expires_at__lt=timezone.now())
    count = expired.count()
    if count:
        expired.delete()
        logger.info(f"Cleaned up {count} expired shipping rate quotes")
