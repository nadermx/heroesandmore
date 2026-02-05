from datetime import timedelta
import logging
import stripe
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Order

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@shared_task
def expire_unpaid_orders():
    """Cancel unpaid orders that have been pending too long and release listings."""
    cutoff = timezone.now() - timedelta(hours=settings.ORDER_PAYMENT_TIMEOUT_HOURS)

    orders = Order.objects.filter(
        status__in=['pending', 'payment_failed'],
        created__lt=cutoff
    ).select_related('listing')

    expired_count = 0

    for order in orders:
        try:
            if order.stripe_payment_intent:
                try:
                    stripe.PaymentIntent.cancel(order.stripe_payment_intent)
                except Exception as e:
                    logger.warning(
                        "Failed to cancel PaymentIntent %s: %s",
                        order.stripe_payment_intent,
                        e
                    )

            order.status = 'cancelled'
            order.save(update_fields=['status', 'updated'])

            if order.listing and order.listing.status == 'sold':
                order.listing.status = 'active'
                order.listing.save(update_fields=['status'])

            expired_count += 1
        except Exception as e:
            logger.exception("Error expiring order %s: %s", order.id, e)

    if expired_count:
        logger.info("Expired %s unpaid orders", expired_count)

    return expired_count
