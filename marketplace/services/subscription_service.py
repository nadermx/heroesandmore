"""
Internal Subscription Billing Service

Handles subscription billing using PaymentIntents instead of Stripe Billing.
Uses the unified Profile.stripe_customer_id for all payments.
"""
import stripe
import logging
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Internal subscription billing using PaymentIntents.

    Key differences from Stripe Billing:
    - Uses Profile.stripe_customer_id (unified customer for all payments)
    - Charges via PaymentIntent with off_session=True for renewals
    - Renewal logic handled by Celery tasks, not Stripe webhooks
    """

    @staticmethod
    def get_or_create_stripe_customer(user):
        """
        Get or create unified Stripe customer from Profile.
        This customer is used for both marketplace purchases and subscriptions.
        """
        profile = user.profile

        if profile.stripe_customer_id:
            try:
                return stripe.Customer.retrieve(profile.stripe_customer_id)
            except stripe.error.InvalidRequestError:
                # Customer was deleted, create new one
                pass

        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip() or user.username,
            metadata={
                'user_id': user.id,
                'username': user.username,
            }
        )

        profile.stripe_customer_id = customer.id
        profile.save(update_fields=['stripe_customer_id'])

        return customer

    @staticmethod
    def subscribe(user, tier, payment_method_id):
        """
        Subscribe user to a tier. Charges immediately for paid tiers.

        Args:
            user: Django User object
            tier: Tier name ('basic', 'featured', 'premium')
            payment_method_id: Stripe PaymentMethod ID

        Returns:
            SellerSubscription object

        Raises:
            ValueError: Invalid tier
            stripe.error.CardError: Payment declined
        """
        from seller_tools.models import SellerSubscription, SubscriptionBillingHistory
        from marketplace.models import PaymentMethod

        tier_info = SellerSubscription.TIER_DETAILS.get(tier)
        if not tier_info:
            raise ValueError(f"Invalid tier: {tier}")

        if tier == 'starter':
            raise ValueError("Cannot subscribe to starter tier - it's free")

        # Get or create subscription record
        subscription, _ = SellerSubscription.objects.get_or_create(
            user=user,
            defaults={'tier': 'starter'}
        )

        # Get or create Stripe customer
        customer = SubscriptionService.get_or_create_stripe_customer(user)

        # Attach payment method to customer
        stripe.PaymentMethod.attach(payment_method_id, customer=customer.id)

        # Set as default for future charges
        stripe.Customer.modify(
            customer.id,
            invoice_settings={'default_payment_method': payment_method_id}
        )

        # Save/update local PaymentMethod record
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        payment_method, _ = PaymentMethod.objects.update_or_create(
            user=user,
            stripe_payment_method_id=payment_method_id,
            defaults={
                'card_brand': pm.card.brand,
                'card_last4': pm.card.last4,
                'card_exp_month': pm.card.exp_month,
                'card_exp_year': pm.card.exp_year,
                'is_default': True,
            }
        )

        # Mark other payment methods as non-default
        PaymentMethod.objects.filter(user=user).exclude(pk=payment_method.pk).update(is_default=False)

        # Calculate billing period
        now = timezone.now()
        period_start = now
        period_end = now + timedelta(days=30)
        amount_cents = int(tier_info['price'] * 100)

        # Charge immediately
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                customer=customer.id,
                payment_method=payment_method_id,
                off_session=False,  # User is present for initial subscription
                confirm=True,
                metadata={
                    'type': 'subscription',
                    'subscription_id': subscription.id,
                    'user_id': user.id,
                    'tier': tier,
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat(),
                },
                description=f"HeroesAndMore {tier_info['name']} Subscription",
            )

            if payment_intent.status == 'succeeded':
                # Update subscription
                with transaction.atomic():
                    subscription.tier = tier
                    subscription.subscription_status = 'active'
                    subscription.current_period_start = period_start
                    subscription.current_period_end = period_end
                    subscription.last_billed_at = now
                    subscription.last_payment_intent_id = payment_intent.id
                    subscription.failed_payment_attempts = 0
                    subscription.next_retry_at = None
                    subscription.grace_period_end = None
                    subscription.default_payment_method = payment_method
                    subscription.max_active_listings = tier_info['max_listings']
                    subscription.commission_rate = tier_info['commission_rate']
                    subscription.featured_slots = tier_info['featured_slots']
                    subscription.cancel_at_period_end = False
                    subscription.save()

                    # Record billing history
                    SubscriptionBillingHistory.objects.create(
                        subscription=subscription,
                        transaction_type='charge',
                        amount=tier_info['price'],
                        tier=tier,
                        status='succeeded',
                        stripe_payment_intent_id=payment_intent.id,
                        period_start=period_start,
                        period_end=period_end,
                    )

                logger.info(f"User {user.id} subscribed to {tier} tier")
                return subscription

            elif payment_intent.status == 'requires_action':
                # 3D Secure required - caller should handle this
                raise stripe.error.CardError(
                    message="Additional authentication required",
                    param=None,
                    code='authentication_required',
                    http_body=None,
                    http_status=None,
                    json_body={'payment_intent': payment_intent.id}
                )

        except stripe.error.CardError as e:
            logger.warning(f"Payment failed for user {user.id} subscribing to {tier}: {e}")
            raise

        return subscription

    @staticmethod
    def charge_renewal(subscription):
        """
        Charge subscription renewal. Called by Celery task.
        Uses off_session=True since user is not present.

        Args:
            subscription: SellerSubscription object

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        from seller_tools.models import SubscriptionBillingHistory

        if subscription.tier == 'starter':
            return True, None

        tier_info = subscription.get_tier_info()
        user = subscription.user
        profile = user.profile

        if not profile.stripe_customer_id:
            return False, "No Stripe customer ID"

        if not subscription.default_payment_method:
            return False, "No payment method on file"

        payment_method_id = subscription.default_payment_method.stripe_payment_method_id
        amount_cents = int(tier_info['price'] * 100)

        now = timezone.now()
        period_start = now
        period_end = now + timedelta(days=30)

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                customer=profile.stripe_customer_id,
                payment_method=payment_method_id,
                off_session=True,
                confirm=True,
                metadata={
                    'type': 'subscription_renewal',
                    'subscription_id': subscription.id,
                    'user_id': user.id,
                    'tier': subscription.tier,
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat(),
                },
                description=f"HeroesAndMore {tier_info['name']} Subscription Renewal",
            )

            if payment_intent.status == 'succeeded':
                with transaction.atomic():
                    subscription.subscription_status = 'active'
                    subscription.current_period_start = period_start
                    subscription.current_period_end = period_end
                    subscription.last_billed_at = now
                    subscription.last_payment_intent_id = payment_intent.id
                    subscription.failed_payment_attempts = 0
                    subscription.next_retry_at = None
                    subscription.grace_period_end = None
                    subscription.save()

                    SubscriptionBillingHistory.objects.create(
                        subscription=subscription,
                        transaction_type='charge',
                        amount=tier_info['price'],
                        tier=subscription.tier,
                        status='succeeded',
                        stripe_payment_intent_id=payment_intent.id,
                        period_start=period_start,
                        period_end=period_end,
                    )

                logger.info(f"Renewed subscription {subscription.id} for user {user.id}")
                return True, None

            else:
                error_msg = f"PaymentIntent status: {payment_intent.status}"
                SubscriptionService._handle_failed_payment(
                    subscription, error_msg, period_start, period_end
                )
                return False, error_msg

        except stripe.error.CardError as e:
            error_msg = str(e.user_message or e)
            SubscriptionService._handle_failed_payment(
                subscription, error_msg, period_start, period_end
            )
            return False, error_msg

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Unexpected error renewing subscription {subscription.id}")
            SubscriptionService._handle_failed_payment(
                subscription, error_msg, period_start, period_end
            )
            return False, error_msg

    @staticmethod
    def _handle_failed_payment(subscription, error_message, period_start, period_end):
        """Handle failed payment - set retry schedule and grace period"""
        from seller_tools.models import SubscriptionBillingHistory

        grace_days = getattr(settings, 'SUBSCRIPTION_GRACE_PERIOD_DAYS', 7)
        max_retries = getattr(settings, 'SUBSCRIPTION_MAX_RETRY_ATTEMPTS', 4)
        retry_intervals = getattr(settings, 'SUBSCRIPTION_RETRY_INTERVALS', [1, 3, 5, 7])

        now = timezone.now()
        attempts = subscription.failed_payment_attempts + 1

        with transaction.atomic():
            subscription.failed_payment_attempts = attempts
            subscription.subscription_status = 'past_due'

            # Set grace period on first failure
            if not subscription.grace_period_end:
                subscription.grace_period_end = now + timedelta(days=grace_days)

            # Schedule next retry
            if attempts < max_retries:
                retry_days = retry_intervals[min(attempts - 1, len(retry_intervals) - 1)]
                subscription.next_retry_at = now + timedelta(days=retry_days)
            else:
                subscription.next_retry_at = None

            subscription.save()

            # Record failed billing attempt
            SubscriptionBillingHistory.objects.create(
                subscription=subscription,
                transaction_type='charge',
                amount=subscription.get_tier_info()['price'],
                tier=subscription.tier,
                status='failed',
                stripe_payment_intent_id='',
                period_start=period_start,
                period_end=period_end,
                failure_reason=error_message,
            )

        logger.warning(
            f"Payment failed for subscription {subscription.id}, "
            f"attempt {attempts}/{max_retries}, error: {error_message}"
        )

    @staticmethod
    def change_tier(user, new_tier, prorate=True):
        """
        Change subscription tier (upgrade or downgrade).

        For upgrades: Charge prorated difference immediately.
        For downgrades: Apply at end of billing period.

        Args:
            user: Django User object
            new_tier: New tier name
            prorate: Whether to prorate (charge/credit difference)

        Returns:
            SellerSubscription object
        """
        from seller_tools.models import SellerSubscription, SubscriptionBillingHistory

        subscription = SellerSubscription.objects.get(user=user)
        old_tier = subscription.tier

        if old_tier == new_tier:
            raise ValueError("Already on this tier")

        new_tier_info = SellerSubscription.TIER_DETAILS.get(new_tier)
        if not new_tier_info:
            raise ValueError(f"Invalid tier: {new_tier}")

        # Starter tier downgrade - just update at period end or immediately if free
        if new_tier == 'starter':
            subscription.cancel_at_period_end = True
            subscription.save(update_fields=['cancel_at_period_end', 'updated'])
            logger.info(f"User {user.id} downgrading to starter at period end")
            return subscription

        old_tier_info = SellerSubscription.TIER_DETAILS.get(old_tier)
        now = timezone.now()

        # Calculate proration if upgrading mid-cycle
        if prorate and subscription.current_period_end and old_tier != 'starter':
            days_remaining = (subscription.current_period_end - now).days
            if days_remaining > 0:
                # Calculate daily rates
                old_daily = old_tier_info['price'] / Decimal('30')
                new_daily = new_tier_info['price'] / Decimal('30')
                proration_amount = (new_daily - old_daily) * Decimal(days_remaining)

                if proration_amount > 0:
                    # Charge the difference for upgrade
                    profile = user.profile
                    if not profile.stripe_customer_id or not subscription.default_payment_method:
                        raise ValueError("Payment method required for upgrade")

                    amount_cents = int(proration_amount * 100)

                    payment_intent = stripe.PaymentIntent.create(
                        amount=amount_cents,
                        currency='usd',
                        customer=profile.stripe_customer_id,
                        payment_method=subscription.default_payment_method.stripe_payment_method_id,
                        off_session=False,
                        confirm=True,
                        metadata={
                            'type': 'subscription_proration',
                            'subscription_id': subscription.id,
                            'user_id': user.id,
                            'old_tier': old_tier,
                            'new_tier': new_tier,
                        },
                        description=f"HeroesAndMore tier upgrade: {old_tier} to {new_tier}",
                    )

                    if payment_intent.status == 'succeeded':
                        SubscriptionBillingHistory.objects.create(
                            subscription=subscription,
                            transaction_type='proration_charge',
                            amount=proration_amount,
                            tier=new_tier,
                            status='succeeded',
                            stripe_payment_intent_id=payment_intent.id,
                            period_start=now,
                            period_end=subscription.current_period_end,
                        )

        # Update subscription to new tier
        subscription.tier = new_tier
        subscription.max_active_listings = new_tier_info['max_listings']
        subscription.commission_rate = new_tier_info['commission_rate']
        subscription.featured_slots = new_tier_info['featured_slots']
        subscription.cancel_at_period_end = False

        # For starter to paid, set initial period
        if old_tier == 'starter':
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
            subscription.subscription_status = 'active'

        subscription.save()

        logger.info(f"User {user.id} changed tier from {old_tier} to {new_tier}")
        return subscription

    @staticmethod
    def cancel(user, at_period_end=True):
        """
        Cancel subscription.

        Args:
            user: Django User object
            at_period_end: If True, downgrade at end of billing period.
                          If False, downgrade immediately.

        Returns:
            SellerSubscription object
        """
        from seller_tools.models import SellerSubscription

        subscription = SellerSubscription.objects.get(user=user)

        if subscription.tier == 'starter':
            return subscription

        if at_period_end:
            subscription.cancel_at_period_end = True
            subscription.save(update_fields=['cancel_at_period_end', 'updated'])
            logger.info(f"User {user.id} subscription will cancel at period end")
        else:
            SubscriptionService._downgrade_to_starter(subscription)
            logger.info(f"User {user.id} subscription cancelled immediately")

        return subscription

    @staticmethod
    def reactivate(user):
        """
        Reactivate a subscription that was set to cancel.

        Returns:
            SellerSubscription object
        """
        from seller_tools.models import SellerSubscription

        subscription = SellerSubscription.objects.get(user=user)

        if not subscription.cancel_at_period_end:
            return subscription

        subscription.cancel_at_period_end = False
        subscription.save(update_fields=['cancel_at_period_end', 'updated'])

        logger.info(f"User {user.id} reactivated subscription")
        return subscription

    @staticmethod
    def _downgrade_to_starter(subscription):
        """Downgrade subscription to starter tier"""
        from seller_tools.models import SellerSubscription

        starter_info = SellerSubscription.TIER_DETAILS['starter']

        subscription.tier = 'starter'
        subscription.max_active_listings = starter_info['max_listings']
        subscription.commission_rate = starter_info['commission_rate']
        subscription.featured_slots = starter_info['featured_slots']
        subscription.subscription_status = 'canceled'
        subscription.cancel_at_period_end = False
        subscription.current_period_end = None
        subscription.next_retry_at = None
        subscription.grace_period_end = None
        subscription.failed_payment_attempts = 0
        subscription.save()

    @staticmethod
    def expire_grace_period(subscription):
        """
        Called when grace period ends without successful payment.
        Downgrades to starter tier.
        """
        logger.info(f"Grace period expired for subscription {subscription.id}")
        SubscriptionService._downgrade_to_starter(subscription)

    @staticmethod
    def process_period_end_cancellations():
        """
        Process subscriptions set to cancel at period end.
        Called by Celery task after renewal processing.
        """
        from seller_tools.models import SellerSubscription

        now = timezone.now()
        subscriptions = SellerSubscription.objects.filter(
            cancel_at_period_end=True,
            current_period_end__lte=now,
        ).exclude(tier='starter')

        count = 0
        for subscription in subscriptions:
            SubscriptionService._downgrade_to_starter(subscription)
            count += 1

        if count:
            logger.info(f"Processed {count} end-of-period cancellations")

        return count

    @staticmethod
    def get_billing_history(user, limit=20):
        """Get billing history for a user"""
        from seller_tools.models import SellerSubscription, SubscriptionBillingHistory

        try:
            subscription = SellerSubscription.objects.get(user=user)
            return SubscriptionBillingHistory.objects.filter(
                subscription=subscription
            ).order_by('-created')[:limit]
        except SellerSubscription.DoesNotExist:
            return []

    @staticmethod
    def calculate_proration(subscription, new_tier):
        """
        Calculate proration amount for tier change.

        Returns:
            dict with keys: amount, days_remaining, is_upgrade
        """
        from seller_tools.models import SellerSubscription

        if subscription.tier == 'starter' or not subscription.current_period_end:
            new_tier_info = SellerSubscription.TIER_DETAILS.get(new_tier)
            return {
                'amount': new_tier_info['price'],
                'days_remaining': 30,
                'is_upgrade': True,
            }

        now = timezone.now()
        days_remaining = max(0, (subscription.current_period_end - now).days)

        old_tier_info = SellerSubscription.TIER_DETAILS.get(subscription.tier)
        new_tier_info = SellerSubscription.TIER_DETAILS.get(new_tier)

        old_daily = old_tier_info['price'] / Decimal('30')
        new_daily = new_tier_info['price'] / Decimal('30')

        proration = (new_daily - old_daily) * Decimal(days_remaining)

        return {
            'amount': abs(proration),
            'days_remaining': days_remaining,
            'is_upgrade': proration > 0,
        }
