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


@shared_task
def poll_usps_tracking():
    """Poll USPS tracking API for shipped orders with USPS tracking numbers.

    USPS has no webhooks, so we poll every 2 hours for status updates.
    Only checks orders that are in 'shipped' status with a USPS carrier.
    """
    from django.conf import settings
    if getattr(settings, 'SHIPPING_PROVIDER', 'usps') != 'usps':
        return

    from marketplace.models import Order
    from marketplace.services.usps_service import USPSService

    orders = Order.objects.filter(
        status='shipped',
        tracking_number__isnull=False,
        tracking_carrier__iexact='USPS',
    ).exclude(tracking_number='')

    updated = 0
    for order in orders:
        try:
            result = USPSService.get_tracking(order.tracking_number)
            new_status = result.get('status')

            if not new_status or new_status == 'unknown':
                continue

            # Only advance status, never go backwards
            status_order = ['pending', 'payment_failed', 'paid', 'shipped', 'delivered', 'completed']
            try:
                current_idx = status_order.index(order.status)
                new_idx = status_order.index(new_status)
            except ValueError:
                continue

            if new_idx <= current_idx:
                continue

            order.status = new_status
            update_fields = ['status', 'updated']

            if new_status == 'delivered' and not order.delivered_at:
                order.delivered_at = timezone.now()
                update_fields.append('delivered_at')

            order.save(update_fields=update_fields)
            updated += 1
            logger.info(f"Order #{order.id} updated to {new_status} via USPS tracking poll")

            # Send push notification on delivery
            if new_status == 'delivered' and order.buyer:
                try:
                    from alerts.tasks import send_order_notifications
                    send_order_notifications.delay(order.id, 'delivered')
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"USPS tracking poll failed for order #{order.id}: {e}")
            continue

    if updated:
        logger.info(f"USPS tracking poll: updated {updated} orders")
