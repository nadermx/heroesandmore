"""
Celery tasks for internal subscription billing and bulk imports.
"""
import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task
def process_subscription_renewals():
    """
    Daily task (2 AM) - Process subscription renewals.

    Finds all subscriptions where current_period_end is in the past
    and attempts to charge them.
    """
    from seller_tools.models import SellerSubscription
    from marketplace.services.subscription_service import SubscriptionService

    now = timezone.now()

    # Find subscriptions due for renewal
    # - Not on starter tier
    # - Period has ended
    # - Not already set to cancel
    # - Not in past_due status (handled by retry task)
    subscriptions = SellerSubscription.objects.filter(
        current_period_end__lte=now,
        cancel_at_period_end=False,
        subscription_status='active',
    ).exclude(tier='starter').select_related('user', 'default_payment_method')

    succeeded = 0
    failed = 0

    for subscription in subscriptions:
        try:
            success, error = SubscriptionService.charge_renewal(subscription)
            if success:
                succeeded += 1
                logger.info(f"Renewed subscription {subscription.id} for user {subscription.user_id}")
            else:
                failed += 1
                logger.warning(
                    f"Failed to renew subscription {subscription.id}: {error}"
                )
                # Send notification about failed payment
                send_payment_failed_notification.delay(subscription.id, error)
        except Exception as e:
            failed += 1
            logger.exception(f"Error renewing subscription {subscription.id}: {e}")

    # Process cancellations scheduled for end of period
    cancelled = SubscriptionService.process_period_end_cancellations()

    logger.info(
        f"Subscription renewal complete: {succeeded} succeeded, "
        f"{failed} failed, {cancelled} cancelled"
    )

    return {
        'succeeded': succeeded,
        'failed': failed,
        'cancelled': cancelled,
    }


@shared_task
def process_single_renewal(subscription_id):
    """
    Process a single subscription renewal.
    Can be called manually or for immediate retry.
    """
    from seller_tools.models import SellerSubscription
    from marketplace.services.subscription_service import SubscriptionService

    try:
        subscription = SellerSubscription.objects.select_related(
            'user', 'default_payment_method'
        ).get(id=subscription_id)
    except SellerSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return {'success': False, 'error': 'Subscription not found'}

    success, error = SubscriptionService.charge_renewal(subscription)

    if success:
        logger.info(f"Successfully renewed subscription {subscription_id}")
    else:
        logger.warning(f"Failed to renew subscription {subscription_id}: {error}")
        send_payment_failed_notification.delay(subscription_id, error)

    return {'success': success, 'error': error}


@shared_task
def retry_failed_payments():
    """
    Hourly task - Retry failed subscription payments.

    Finds subscriptions with status 'past_due' that are scheduled
    for retry (next_retry_at <= now).
    """
    from seller_tools.models import SellerSubscription
    from marketplace.services.subscription_service import SubscriptionService

    now = timezone.now()

    # Find subscriptions ready for retry
    subscriptions = SellerSubscription.objects.filter(
        subscription_status='past_due',
        next_retry_at__lte=now,
    ).exclude(tier='starter').select_related('user', 'default_payment_method')

    succeeded = 0
    failed = 0

    for subscription in subscriptions:
        try:
            success, error = SubscriptionService.charge_renewal(subscription)
            if success:
                succeeded += 1
                logger.info(
                    f"Retry succeeded for subscription {subscription.id}"
                )
                # Send recovery notification
                send_payment_recovered_notification.delay(subscription.id)
            else:
                failed += 1
                logger.warning(
                    f"Retry failed for subscription {subscription.id}: {error}"
                )
                send_payment_failed_notification.delay(subscription.id, error)
        except Exception as e:
            failed += 1
            logger.exception(
                f"Error retrying subscription {subscription.id}: {e}"
            )

    if succeeded or failed:
        logger.info(
            f"Payment retry complete: {succeeded} succeeded, {failed} failed"
        )

    return {'succeeded': succeeded, 'failed': failed}


@shared_task
def expire_grace_periods():
    """
    Daily task (3 AM) - Expire subscriptions past grace period.

    Finds subscriptions where grace_period_end has passed and
    downgrades them to starter tier.
    """
    from seller_tools.models import SellerSubscription
    from marketplace.services.subscription_service import SubscriptionService

    now = timezone.now()

    # Find subscriptions with expired grace period
    subscriptions = SellerSubscription.objects.filter(
        subscription_status='past_due',
        grace_period_end__lte=now,
    ).exclude(tier='starter')

    expired = 0

    for subscription in subscriptions:
        try:
            old_tier = subscription.tier
            SubscriptionService.expire_grace_period(subscription)
            expired += 1
            logger.info(
                f"Grace period expired for subscription {subscription.id}, "
                f"downgraded from {old_tier} to starter"
            )
            # Send notification
            send_subscription_expired_notification.delay(
                subscription.id, old_tier
            )
        except Exception as e:
            logger.exception(
                f"Error expiring subscription {subscription.id}: {e}"
            )

    if expired:
        logger.info(f"Expired {expired} subscriptions past grace period")

    return {'expired': expired}


@shared_task
def send_renewal_reminders():
    """
    Daily task (10 AM) - Send renewal reminders.

    Sends email reminders 3 days before subscription renewal.
    """
    from seller_tools.models import SellerSubscription
    from datetime import timedelta

    now = timezone.now()
    reminder_date = now + timedelta(days=3)

    # Find subscriptions renewing in 3 days
    subscriptions = SellerSubscription.objects.filter(
        current_period_end__date=reminder_date.date(),
        subscription_status='active',
    ).exclude(tier='starter')

    sent = 0
    for subscription in subscriptions:
        try:
            send_subscription_renewal_notification.delay(subscription.id)
            sent += 1
        except Exception as e:
            logger.exception(
                f"Error sending renewal reminder for subscription {subscription.id}: {e}"
            )

    if sent:
        logger.info(f"Sent {sent} renewal reminders")

    return {'sent': sent}


@shared_task
def process_bulk_import(bulk_import_id):
    """Process a bulk import and create draft listings."""
    from seller_tools.models import BulkImport, BulkImportRow
    from marketplace.models import Listing
    from items.models import Category

    bulk_import = BulkImport.objects.filter(id=bulk_import_id).select_related('user').first()
    if not bulk_import:
        logger.error("Bulk import %s not found", bulk_import_id)
        return {'success': False, 'error': 'Bulk import not found'}

    if bulk_import.status not in ['validating', 'partial', 'processing', 'pending']:
        return {'success': False, 'error': 'Import is not ready'}

    rows = bulk_import.rows.all().order_by('row_number')

    success_count = 0
    error_count = 0
    processed_rows = 0

    for row in rows:
        if row.status == 'success':
            continue

        data = row.data or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        category_slug = (data.get('category') or '').strip()
        condition = (data.get('condition') or '').strip()
        price = data.get('price')
        shipping_price = data.get('shipping_price') or 0
        listing_type = (data.get('listing_type') or 'fixed').strip()
        allow_offers = str(data.get('allow_offers', '')).lower() in ['1', 'true', 'yes', 'on']
        grading_service = (data.get('grading_service') or '').strip()
        grade = (data.get('grade') or '').strip()
        cert_number = (data.get('cert_number') or '').strip()
        auction_duration = data.get('auction_duration_days') or ''

        if not title:
            row.status = 'error'
            row.error_message = 'Missing title'
            row.save(update_fields=['status', 'error_message'])
            error_count += 1
            continue

        if not description:
            row.status = 'error'
            row.error_message = 'Missing description'
            row.save(update_fields=['status', 'error_message'])
            error_count += 1
            continue

        category = None
        if category_slug:
            category = Category.objects.filter(slug=category_slug).first()

        if not category:
            row.status = 'error'
            row.error_message = 'Invalid or missing category'
            row.save(update_fields=['status', 'error_message'])
            error_count += 1
            continue

        if not condition:
            row.status = 'error'
            row.error_message = 'Missing condition'
            row.save(update_fields=['status', 'error_message'])
            error_count += 1
            continue

        if not price:
            row.status = 'error'
            row.error_message = 'Missing price'
            row.save(update_fields=['status', 'error_message'])
            error_count += 1
            continue

        # Parse quantity (fixed-price only, default 1)
        quantity = 1
        raw_qty = (data.get('quantity') or '').strip()
        if raw_qty:
            try:
                quantity = max(1, int(raw_qty))
            except (ValueError, TypeError):
                quantity = 1

        listing = Listing.objects.create(
            seller=bulk_import.user,
            title=title,
            description=description,
            category=category,
            condition=condition,
            price=price,
            shipping_price=shipping_price,
            listing_type=listing_type if listing_type in ['fixed', 'auction'] else 'fixed',
            allow_offers=allow_offers,
            grading_service=grading_service,
            grade=grade,
            cert_number=cert_number,
            quantity=quantity if listing_type == 'fixed' else 1,
            status='draft',
        )

        if listing.listing_type == 'auction' and auction_duration:
            try:
                days = int(auction_duration)
                listing.auction_end = timezone.now() + timedelta(days=days)
                listing.starting_bid = listing.price
                listing.save(update_fields=['auction_end', 'starting_bid'])
            except Exception:
                pass

        row.listing = listing
        row.status = 'success'
        row.error_message = ''
        row.save(update_fields=['listing', 'status', 'error_message'])

        success_count += 1
        processed_rows += 1

    bulk_import.processed_rows = processed_rows
    bulk_import.success_count = success_count
    bulk_import.error_count = error_count
    bulk_import.status = 'completed' if error_count == 0 else 'partial'
    bulk_import.completed_at = timezone.now()
    bulk_import.save(update_fields=[
        'processed_rows', 'success_count', 'error_count',
        'status', 'completed_at'
    ])

    return {
        'success': True,
        'processed': processed_rows,
        'success_count': success_count,
        'error_count': error_count,
    }


@shared_task
def send_subscription_renewal_notification(subscription_id):
    from seller_tools.models import SellerSubscription
    subscription = SellerSubscription.objects.filter(id=subscription_id).select_related('user').first()
    if not subscription:
        return

    subject = 'Your HeroesAndMore subscription renews soon'
    context = {
        'subscription': subscription,
        'user': subscription.user,
    }
    body = render_to_string('seller_tools/emails/renewal_reminder.txt', context)
    html_body = render_to_string('seller_tools/emails/renewal_reminder.html', context)

    send_mail(
        subject,
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroesandmore.com'),
        [subscription.user.email],
        html_message=html_body,
        fail_silently=True,
    )


@shared_task
def send_payment_failed_notification(subscription_id, error):
    from seller_tools.models import SellerSubscription
    subscription = SellerSubscription.objects.filter(id=subscription_id).select_related('user').first()
    if not subscription:
        return

    subject = 'Payment failed for your HeroesAndMore subscription'
    context = {
        'subscription': subscription,
        'user': subscription.user,
        'error': error,
    }
    body = render_to_string('seller_tools/emails/payment_failed.txt', context)
    html_body = render_to_string('seller_tools/emails/payment_failed.html', context)

    send_mail(
        subject,
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroesandmore.com'),
        [subscription.user.email],
        html_message=html_body,
        fail_silently=True,
    )


@shared_task
def send_payment_recovered_notification(subscription_id):
    from seller_tools.models import SellerSubscription
    subscription = SellerSubscription.objects.filter(id=subscription_id).select_related('user').first()
    if not subscription:
        return

    subject = 'Payment recovered for your HeroesAndMore subscription'
    context = {
        'subscription': subscription,
        'user': subscription.user,
    }
    body = render_to_string('seller_tools/emails/payment_recovered.txt', context)
    html_body = render_to_string('seller_tools/emails/payment_recovered.html', context)

    send_mail(
        subject,
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroesandmore.com'),
        [subscription.user.email],
        html_message=html_body,
        fail_silently=True,
    )


@shared_task
def send_subscription_expired_notification(subscription_id, old_tier):
    from seller_tools.models import SellerSubscription
    subscription = SellerSubscription.objects.filter(id=subscription_id).select_related('user').first()
    if not subscription:
        return

    subject = 'Your HeroesAndMore subscription has expired'
    context = {
        'subscription': subscription,
        'user': subscription.user,
        'old_tier': old_tier,
    }
    body = render_to_string('seller_tools/emails/subscription_expired.txt', context)
    html_body = render_to_string('seller_tools/emails/subscription_expired.html', context)

    send_mail(
        subject,
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@heroesandmore.com'),
        [subscription.user.email],
        html_message=html_body,
        fail_silently=True,
    )
