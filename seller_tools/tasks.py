"""
Celery tasks for internal subscription billing.

These tasks handle:
- Nightly subscription renewal processing
- Failed payment retries
- Grace period expiration
- Renewal reminder emails
"""
import logging
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
        cancel_at_period_end=False,
    ).exclude(tier='starter').select_related('user')

    sent = 0

    for subscription in subscriptions:
        try:
            user = subscription.user
            tier_info = subscription.get_tier_info()

            subject = f"Your {tier_info['name']} subscription renews in 3 days"

            context = {
                'user': user,
                'subscription': subscription,
                'tier_info': tier_info,
                'renewal_date': subscription.current_period_end,
            }

            html_message = render_to_string(
                'seller_tools/emails/renewal_reminder.html', context
            )
            plain_message = render_to_string(
                'seller_tools/emails/renewal_reminder.txt', context
            )

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True,
            )

            sent += 1

        except Exception as e:
            logger.error(
                f"Error sending renewal reminder to user {subscription.user_id}: {e}"
            )

    if sent:
        logger.info(f"Sent {sent} renewal reminders")

    return {'sent': sent}


@shared_task
def send_payment_failed_notification(subscription_id, error_message):
    """Send notification when subscription payment fails."""
    from seller_tools.models import SellerSubscription

    try:
        subscription = SellerSubscription.objects.select_related('user').get(
            id=subscription_id
        )
    except SellerSubscription.DoesNotExist:
        return

    user = subscription.user
    tier_info = subscription.get_tier_info()

    subject = f"Payment failed for your {tier_info['name']} subscription"

    context = {
        'user': user,
        'subscription': subscription,
        'tier_info': tier_info,
        'error_message': error_message,
        'grace_period_end': subscription.grace_period_end,
        'update_payment_url': f"{settings.SITE_URL}/seller/subscription/payment-methods/",
    }

    try:
        html_message = render_to_string(
            'seller_tools/emails/payment_failed.html', context
        )
        plain_message = render_to_string(
            'seller_tools/emails/payment_failed.txt', context
        )

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        logger.error(
            f"Error sending payment failed notification to user {user.id}: {e}"
        )


@shared_task
def send_payment_recovered_notification(subscription_id):
    """Send notification when payment succeeds after previous failure."""
    from seller_tools.models import SellerSubscription

    try:
        subscription = SellerSubscription.objects.select_related('user').get(
            id=subscription_id
        )
    except SellerSubscription.DoesNotExist:
        return

    user = subscription.user
    tier_info = subscription.get_tier_info()

    subject = f"Payment successful - Your {tier_info['name']} subscription is active"

    context = {
        'user': user,
        'subscription': subscription,
        'tier_info': tier_info,
    }

    try:
        html_message = render_to_string(
            'seller_tools/emails/payment_recovered.html', context
        )
        plain_message = render_to_string(
            'seller_tools/emails/payment_recovered.txt', context
        )

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        logger.error(
            f"Error sending payment recovered notification to user {user.id}: {e}"
        )


@shared_task
def send_subscription_expired_notification(subscription_id, old_tier):
    """Send notification when subscription expires after grace period."""
    from seller_tools.models import SellerSubscription

    try:
        subscription = SellerSubscription.objects.select_related('user').get(
            id=subscription_id
        )
    except SellerSubscription.DoesNotExist:
        return

    user = subscription.user

    subject = "Your seller subscription has expired"

    context = {
        'user': user,
        'old_tier': old_tier,
        'subscription_url': f"{settings.SITE_URL}/seller/subscription/",
    }

    try:
        html_message = render_to_string(
            'seller_tools/emails/subscription_expired.html', context
        )
        plain_message = render_to_string(
            'seller_tools/emails/subscription_expired.txt', context
        )

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        logger.error(
            f"Error sending subscription expired notification to user {user.id}: {e}"
        )
