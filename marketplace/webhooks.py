import stripe
import json
import logging
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from marketplace.models import Order, StripeEvent

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks for payments"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        return HttpResponse(status=400)

    # Idempotency check - prevent duplicate processing
    stripe_event, created = StripeEvent.objects.get_or_create(
        stripe_event_id=event.id,
        defaults={
            'event_type': event.type,
            'raw_data': json.loads(payload)
        }
    )

    if not created and stripe_event.processed:
        logger.info(f"Event {event.id} already processed, skipping")
        return HttpResponse(status=200)

    try:
        # Route to handler
        handler = WEBHOOK_HANDLERS.get(event.type)
        if handler:
            handler(event)
            logger.info(f"Processed webhook event: {event.type}")
        else:
            logger.info(f"Unhandled webhook event type: {event.type}")

        stripe_event.processed = True
        stripe_event.processed_at = timezone.now()
        stripe_event.save()

    except Exception as e:
        logger.exception(f"Error processing webhook {event.id}: {e}")
        stripe_event.error_message = str(e)
        stripe_event.save()
        # Return 200 to prevent Stripe from retrying (we logged the error)
        # In production, you might want to return 500 for certain errors

    return HttpResponse(status=200)


def handle_payment_intent_succeeded(event):
    """Handle successful payment"""
    payment_intent = event.data.object
    payment_type = payment_intent.metadata.get('type', '')

    # Handle subscription payments (logged for audit, actual update done in service)
    if payment_type in ['subscription', 'subscription_renewal', 'subscription_proration']:
        subscription_id = payment_intent.metadata.get('subscription_id')
        user_id = payment_intent.metadata.get('user_id')
        tier = payment_intent.metadata.get('tier', '')
        logger.info(
            f"Subscription payment succeeded: type={payment_type}, "
            f"subscription_id={subscription_id}, user_id={user_id}, tier={tier}, "
            f"pi={payment_intent.id}"
        )
        return

    # Handle marketplace order payments
    order_id = payment_intent.metadata.get('order_id')

    if not order_id:
        logger.warning(f"PaymentIntent {payment_intent.id} has no order_id in metadata")
        return

    try:
        order = Order.objects.get(id=order_id)
        order.stripe_payment_status = 'succeeded'
        order.status = 'paid'
        order.paid_at = timezone.now()
        order.save(update_fields=['stripe_payment_status', 'status', 'paid_at', 'updated'])

        logger.info(f"Order {order_id} marked as paid")

        if order.listing and order.listing.status != 'sold':
            order.listing.status = 'sold'
            order.listing.save(update_fields=['status'])

        # Send notifications (async via Celery if available)
        try:
            from alerts.tasks import send_order_notifications
            send_order_notifications.delay(order.id, 'paid')
        except ImportError:
            pass

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for PaymentIntent {payment_intent.id}")


def handle_payment_intent_failed(event):
    """Handle failed payment for both orders and subscriptions"""
    payment_intent = event.data.object
    payment_type = payment_intent.metadata.get('type', '')

    # Handle subscription payment failures (logged for audit)
    if payment_type in ['subscription', 'subscription_renewal']:
        subscription_id = payment_intent.metadata.get('subscription_id')
        user_id = payment_intent.metadata.get('user_id')
        error = payment_intent.last_payment_error
        error_msg = error.message if error else 'Unknown error'

        logger.warning(
            f"Subscription payment failed: subscription_id={subscription_id}, "
            f"user_id={user_id}, error={error_msg}, pi={payment_intent.id}"
        )
        # Note: Retry scheduling is handled in SubscriptionService._handle_failed_payment
        return

    # Handle order payment failures
    order_id = payment_intent.metadata.get('order_id')

    if not order_id:
        return

    try:
        order = Order.objects.get(id=order_id)
        order.stripe_payment_status = 'failed'
        order.status = 'payment_failed'
        order.save(update_fields=['stripe_payment_status', 'status', 'updated'])

        # Restore listing if it was marked sold
        if order.listing and order.listing.status == 'sold':
            order.listing.status = 'active'
            order.listing.save(update_fields=['status'])

        logger.info(f"Order {order_id} payment failed")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")


def handle_payment_intent_requires_action(event):
    """Handle 3D Secure authentication required"""
    payment_intent = event.data.object
    order_id = payment_intent.metadata.get('order_id')

    if not order_id:
        return

    try:
        order = Order.objects.get(id=order_id)
        order.stripe_payment_status = 'requires_action'
        order.save(update_fields=['stripe_payment_status', 'updated'])
    except Order.DoesNotExist:
        pass


def handle_charge_refunded(event):
    """Handle refund completed"""
    charge = event.data.object
    payment_intent_id = charge.payment_intent

    if not payment_intent_id:
        return

    try:
        order = Order.objects.get(stripe_payment_intent=payment_intent_id)

        # Calculate total refunded
        total_refunded = charge.amount_refunded / 100 if charge.amount_refunded else 0
        order.refund_amount = total_refunded

        if order.refund_amount >= order.amount:
            order.refund_status = 'full'
            order.status = 'refunded'
        else:
            order.refund_status = 'partial'

        order.save(update_fields=['refund_amount', 'refund_status', 'status', 'updated'])
        logger.info(f"Order {order.id} refund processed: ${total_refunded}")

    except Order.DoesNotExist:
        logger.warning(f"No order found for payment_intent {payment_intent_id}")


def handle_charge_dispute_created(event):
    """Handle dispute/chargeback created"""
    dispute = event.data.object
    payment_intent_id = dispute.payment_intent

    if not payment_intent_id:
        return

    try:
        order = Order.objects.get(stripe_payment_intent=payment_intent_id)
        order.status = 'disputed'
        order.save(update_fields=['status', 'updated'])

        logger.warning(f"Dispute created for Order {order.id}")

        # Notify admin
        try:
            from django.core.mail import mail_admins
            mail_admins(
                f"Dispute Created - Order #{order.id}",
                f"A dispute has been filed for order #{order.id}.\n"
                f"Amount: ${dispute.amount / 100:.2f}\n"
                f"Reason: {dispute.reason}\n"
                f"Please respond in the Stripe Dashboard."
            )
        except Exception as e:
            logger.error(f"Failed to send dispute notification: {e}")

    except Order.DoesNotExist:
        logger.warning(f"No order found for dispute on payment_intent {payment_intent_id}")


def handle_transfer_created(event):
    """Handle transfer to seller created"""
    transfer = event.data.object
    order_id = transfer.metadata.get('order_id')

    if not order_id:
        return

    try:
        order = Order.objects.get(id=order_id)
        order.stripe_transfer_id = transfer.id
        order.stripe_transfer_status = 'pending'
        order.seller_payout = transfer.amount / 100
        order.save(update_fields=['stripe_transfer_id', 'stripe_transfer_status', 'seller_payout', 'updated'])
    except Order.DoesNotExist:
        pass


# Webhook handler registry
# Note: Stripe Billing handlers (subscription.*, invoice.*) removed.
# Subscription billing is now handled internally via PaymentIntents and Celery tasks.
WEBHOOK_HANDLERS = {
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_failed,
    'payment_intent.requires_action': handle_payment_intent_requires_action,
    'charge.refunded': handle_charge_refunded,
    'charge.dispute.created': handle_charge_dispute_created,
    'transfer.created': handle_transfer_created,
}


@csrf_exempt
@require_POST
def stripe_connect_webhook(request):
    """Handle Stripe Connect webhooks for seller accounts"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_CONNECT_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.error(f"Connect webhook error: {e}")
        return HttpResponse(status=400)

    # Idempotency check
    stripe_event, created = StripeEvent.objects.get_or_create(
        stripe_event_id=event.id,
        defaults={
            'event_type': event.type,
            'raw_data': json.loads(payload)
        }
    )

    if not created and stripe_event.processed:
        return HttpResponse(status=200)

    try:
        if event.type == 'account.updated':
            handle_account_updated(event)

        stripe_event.processed = True
        stripe_event.processed_at = timezone.now()
        stripe_event.save()

    except Exception as e:
        logger.exception(f"Error processing connect webhook {event.id}: {e}")
        stripe_event.error_message = str(e)
        stripe_event.save()

    return HttpResponse(status=200)


def handle_account_updated(event):
    """Handle Connect account status update"""
    account = event.data.object

    from accounts.models import Profile
    try:
        profile = Profile.objects.get(stripe_account_id=account.id)
        profile.stripe_charges_enabled = account.charges_enabled
        profile.stripe_payouts_enabled = account.payouts_enabled
        profile.stripe_account_complete = (
            account.charges_enabled and
            account.payouts_enabled and
            not account.requirements.currently_due
        )
        profile.save(update_fields=[
            'stripe_charges_enabled',
            'stripe_payouts_enabled',
            'stripe_account_complete'
        ])
        logger.info(f"Updated Connect account status for profile {profile.id}")
    except Profile.DoesNotExist:
        logger.warning(f"No profile found for Connect account {account.id}")
