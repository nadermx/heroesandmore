import stripe
import logging
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class SubscriptionService:
    """Stripe Billing for seller subscriptions"""

    @staticmethod
    def get_price_id(tier):
        """Get Stripe price ID for a tier"""
        price_ids = settings.STRIPE_PRICE_IDS
        return price_ids.get(tier, '')

    @staticmethod
    def get_or_create_customer(user):
        """Get or create Stripe customer for subscription"""
        from seller_tools.models import SellerSubscription

        sub, created = SellerSubscription.objects.get_or_create(
            user=user,
            defaults={'tier': 'starter'}
        )

        if sub.stripe_customer_id:
            try:
                return stripe.Customer.retrieve(sub.stripe_customer_id)
            except stripe.error.InvalidRequestError:
                # Customer deleted, create new
                pass

        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip() or user.username,
            metadata={
                'user_id': user.id,
                'subscription_type': 'seller'
            }
        )

        sub.stripe_customer_id = customer.id
        sub.save(update_fields=['stripe_customer_id'])

        return customer

    @staticmethod
    def create_checkout_session(user, tier, success_url, cancel_url):
        """Create Checkout Session for subscription"""
        price_id = SubscriptionService.get_price_id(tier)
        if not price_id:
            raise ValueError(f"Invalid tier or missing price ID: {tier}")

        customer = SubscriptionService.get_or_create_customer(user)

        session = stripe.checkout.Session.create(
            customer=customer.id,
            mode='subscription',
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': user.id,
                'tier': tier,
            },
            subscription_data={
                'metadata': {
                    'user_id': user.id,
                    'tier': tier,
                }
            }
        )

        return session

    @staticmethod
    def create_subscription(user, tier, payment_method_id):
        """Create subscription directly (after SetupIntent)"""
        price_id = SubscriptionService.get_price_id(tier)
        if not price_id:
            raise ValueError(f"Invalid tier or missing price ID: {tier}")

        customer = SubscriptionService.get_or_create_customer(user)

        # Attach payment method
        stripe.PaymentMethod.attach(payment_method_id, customer=customer.id)
        stripe.Customer.modify(
            customer.id,
            invoice_settings={'default_payment_method': payment_method_id}
        )

        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_id}],
            metadata={
                'user_id': user.id,
                'tier': tier,
            },
            expand=['latest_invoice.payment_intent']
        )

        SubscriptionService.sync_subscription(user, subscription)

        return subscription

    @staticmethod
    def sync_subscription(user, subscription):
        """Sync subscription data from Stripe"""
        from seller_tools.models import SellerSubscription

        sub, _ = SellerSubscription.objects.get_or_create(
            user=user,
            defaults={'tier': 'starter'}
        )

        # Map Stripe status to our status
        status_map = {
            'active': 'active',
            'past_due': 'past_due',
            'canceled': 'canceled',
            'unpaid': 'suspended',
            'trialing': 'active',
            'incomplete': 'inactive',
            'incomplete_expired': 'canceled',
        }

        # Get tier from metadata
        tier = subscription.metadata.get('tier', sub.tier)

        # Get tier info to update limits
        tier_info = SellerSubscription.TIER_DETAILS.get(tier, SellerSubscription.TIER_DETAILS['starter'])

        sub.stripe_subscription_id = subscription.id
        sub.stripe_price_id = subscription['items']['data'][0]['price']['id'] if subscription['items']['data'] else ''
        sub.subscription_status = status_map.get(subscription.status, subscription.status)

        # Only update tier and limits if subscription is active
        if subscription.status == 'active':
            sub.tier = tier
            sub.max_active_listings = tier_info['max_listings']
            sub.commission_rate = tier_info['commission_rate']
            sub.featured_slots = tier_info['featured_slots']

        sub.current_period_start = datetime.fromtimestamp(
            subscription.current_period_start, tz=timezone.utc
        )
        sub.current_period_end = datetime.fromtimestamp(
            subscription.current_period_end, tz=timezone.utc
        )
        sub.cancel_at_period_end = subscription.cancel_at_period_end
        sub.save()

        return sub

    @staticmethod
    def cancel_subscription(user, at_period_end=True):
        """Cancel subscription"""
        from seller_tools.models import SellerSubscription

        try:
            sub = SellerSubscription.objects.get(user=user)
        except SellerSubscription.DoesNotExist:
            return None

        if not sub.stripe_subscription_id:
            return None

        if at_period_end:
            # Cancel at end of billing period
            subscription = stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True
            )
        else:
            # Cancel immediately
            subscription = stripe.Subscription.delete(sub.stripe_subscription_id)

        SubscriptionService.sync_subscription(user, subscription)
        return subscription

    @staticmethod
    def reactivate_subscription(user):
        """Reactivate a subscription set to cancel"""
        from seller_tools.models import SellerSubscription

        try:
            sub = SellerSubscription.objects.get(user=user)
        except SellerSubscription.DoesNotExist:
            return None

        if not sub.stripe_subscription_id:
            return None

        subscription = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=False
        )

        SubscriptionService.sync_subscription(user, subscription)
        return subscription

    @staticmethod
    def change_tier(user, new_tier):
        """Change subscription tier (prorate)"""
        from seller_tools.models import SellerSubscription

        new_price_id = SubscriptionService.get_price_id(new_tier)
        if not new_price_id:
            raise ValueError(f"Invalid tier or missing price ID: {new_tier}")

        try:
            sub = SellerSubscription.objects.get(user=user)
        except SellerSubscription.DoesNotExist:
            raise ValueError("No subscription found")

        if not sub.stripe_subscription_id:
            raise ValueError("No active subscription")

        subscription = stripe.Subscription.retrieve(sub.stripe_subscription_id)

        # Modify the subscription with new price
        updated = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            items=[{
                'id': subscription['items']['data'][0]['id'],
                'price': new_price_id,
            }],
            proration_behavior='create_prorations',
            metadata={'tier': new_tier}
        )

        # Refresh and sync
        subscription = stripe.Subscription.retrieve(sub.stripe_subscription_id)
        SubscriptionService.sync_subscription(user, subscription)

        return subscription

    @staticmethod
    def create_billing_portal_session(user, return_url):
        """Create Stripe Billing Portal session for self-service"""
        from seller_tools.models import SellerSubscription

        try:
            sub = SellerSubscription.objects.get(user=user)
        except SellerSubscription.DoesNotExist:
            raise ValueError("No subscription found")

        if not sub.stripe_customer_id:
            raise ValueError("No Stripe customer")

        return stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=return_url,
        )

    @staticmethod
    def get_subscription_status(user):
        """Get current subscription status from Stripe"""
        from seller_tools.models import SellerSubscription

        try:
            sub = SellerSubscription.objects.get(user=user)
        except SellerSubscription.DoesNotExist:
            return None

        if not sub.stripe_subscription_id:
            return None

        try:
            subscription = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            SubscriptionService.sync_subscription(user, subscription)
            return subscription
        except stripe.error.InvalidRequestError:
            return None
