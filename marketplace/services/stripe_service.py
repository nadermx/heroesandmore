import stripe
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class StripeService:
    """Core Stripe operations for payments"""

    @staticmethod
    def get_or_create_customer(user):
        """Get or create Stripe customer for buyer"""
        profile = user.profile
        if profile.stripe_customer_id:
            try:
                return stripe.Customer.retrieve(profile.stripe_customer_id)
            except stripe.error.InvalidRequestError:
                # Customer was deleted in Stripe, create new one
                pass

        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip() or user.username,
            metadata={'user_id': user.id}
        )
        profile.stripe_customer_id = customer.id
        profile.save(update_fields=['stripe_customer_id'])
        return customer

    # Per-transaction flat fees
    STRIPE_PROCESSING_FEE = Decimal('0.29')   # Stripe's fixed per-txn fee
    SHIPPING_LABEL_FEE = Decimal('0.05')      # Per-order shipping label fee
    PLATFORM_FLAT_FEE = STRIPE_PROCESSING_FEE + SHIPPING_LABEL_FEE  # $0.34 total

    # Trusted seller commission discount (2%)
    TRUSTED_SELLER_DISCOUNT = Decimal('0.02')
    # Minimum commission rate floor
    MIN_COMMISSION_RATE = Decimal('0.0395')

    @staticmethod
    def get_seller_commission_rate(seller):
        """Get seller's commission rate based on subscription tier and trusted status"""
        from seller_tools.models import SellerSubscription
        try:
            sub = SellerSubscription.objects.get(user=seller)
            # Commission rates are stored as percentages (e.g., 12.95)
            rate = sub.commission_rate / 100
        except SellerSubscription.DoesNotExist:
            # Default to starter tier commission
            rate = Decimal('0.1295')

        # Apply trusted seller discount
        if hasattr(seller, 'profile') and seller.profile.is_trusted_seller:
            rate = max(rate - StripeService.TRUSTED_SELLER_DISCOUNT, StripeService.MIN_COMMISSION_RATE)

        return rate

    @staticmethod
    def calculate_platform_fee(price, seller):
        """Calculate platform fee: flat fee + percentage commission.

        For platform accounts, the platform keeps the full price (no seller payout).
        This ensures we always cover Stripe's processing costs ($0.30 + 2.9%)
        even on low-dollar transactions.
        """
        if hasattr(seller, 'profile') and seller.profile.is_platform_account:
            return price
        commission_rate = StripeService.get_seller_commission_rate(seller)
        return (StripeService.PLATFORM_FLAT_FEE + price * commission_rate).quantize(Decimal('0.01'))

    @staticmethod
    def create_payment_intent(order, payment_method_id=None, save_card=False):
        """Create PaymentIntent for order checkout.
        Supports both authenticated buyers and guest checkout.
        """
        seller_profile = order.seller.profile

        # Get or create Stripe customer
        if order.buyer:
            customer = StripeService.get_or_create_customer(order.buyer)
        else:
            # Guest checkout — create ephemeral Stripe customer
            customer = stripe.Customer.create(
                email=order.guest_email,
                name=order.guest_name,
                metadata={'guest_order': True, 'order_id': order.id}
            )

        # Calculate amounts in cents
        total_cents = int(order.amount * 100)

        # Calculate platform fee (flat fee + percentage)
        platform_fee = StripeService.calculate_platform_fee(order.item_price, order.seller)
        platform_fee_cents = int(platform_fee * 100)

        # Build PaymentIntent params
        params = {
            'amount': total_cents,
            'currency': 'usd',
            'customer': customer.id,
            'metadata': {
                'order_id': order.id,
                'listing_id': order.listing_id if order.listing else '',
                'buyer_email': order.buyer_email,
                'seller_id': order.seller.id,
            },
            'description': f"Order #{order.id} - {order.listing.title[:50] if order.listing else 'Order'}",
            'automatic_payment_methods': {'enabled': True},
        }

        # If seller has connected account, set up destination charge
        if seller_profile.stripe_account_id and seller_profile.stripe_charges_enabled:
            params['transfer_data'] = {
                'destination': seller_profile.stripe_account_id,
            }
            params['application_fee_amount'] = platform_fee_cents

        # Attach payment method if provided (for confirming payment)
        if payment_method_id:
            params['payment_method'] = payment_method_id
            params['confirm'] = True
            params['return_url'] = f"{settings.SITE_URL}/marketplace/order/{order.id}/complete/"

            # Only save card for authenticated users
            if save_card and order.buyer:
                params['setup_future_usage'] = 'off_session'

        intent = stripe.PaymentIntent.create(**params)

        # Update order with payment intent details
        order.stripe_payment_intent = intent.id
        order.platform_fee = platform_fee
        order.seller_payout = order.item_price - order.platform_fee
        order.save(update_fields=['stripe_payment_intent', 'platform_fee', 'seller_payout'])

        return intent

    @staticmethod
    def confirm_payment_intent(payment_intent_id, payment_method_id):
        """Confirm a PaymentIntent with a payment method"""
        return stripe.PaymentIntent.confirm(
            payment_intent_id,
            payment_method=payment_method_id,
            return_url=f"{settings.SITE_URL}/marketplace/checkout/complete/"
        )

    @staticmethod
    def retrieve_payment_intent(payment_intent_id):
        """Get PaymentIntent status"""
        return stripe.PaymentIntent.retrieve(payment_intent_id)

    @staticmethod
    def create_refund(order, amount=None, reason='requested_by_customer'):
        """Create refund for an order"""
        from marketplace.models import Refund

        if not order.stripe_payment_intent:
            raise ValueError("Order has no payment intent")

        refund_params = {
            'payment_intent': order.stripe_payment_intent,
            'reason': reason,
            'metadata': {'order_id': order.id}
        }

        if amount:
            refund_params['amount'] = int(amount * 100)

        stripe_refund = stripe.Refund.create(**refund_params)

        # Create refund record
        refund = Refund.objects.create(
            order=order,
            stripe_refund_id=stripe_refund.id,
            amount=Decimal(stripe_refund.amount) / 100,
            reason=reason,
            status=stripe_refund.status,
        )

        # Update order refund tracking
        order.refund_amount = (order.refund_amount or 0) + refund.amount
        order.stripe_refund_id = stripe_refund.id

        if order.refund_amount >= order.amount:
            order.refund_status = 'full'
            order.status = 'refunded'
        else:
            order.refund_status = 'partial'

        order.save(update_fields=['refund_amount', 'refund_status', 'stripe_refund_id', 'status'])

        return stripe_refund

    @staticmethod
    def list_payment_methods(user):
        """List saved payment methods for a customer"""
        profile = user.profile
        if not profile.stripe_customer_id:
            return []

        try:
            methods = stripe.PaymentMethod.list(
                customer=profile.stripe_customer_id,
                type='card'
            )
            return methods.data
        except stripe.error.InvalidRequestError:
            return []

    @staticmethod
    def attach_payment_method(user, payment_method_id, set_default=False):
        """Attach a payment method to customer"""
        customer = StripeService.get_or_create_customer(user)

        pm = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer.id
        )

        if set_default:
            stripe.Customer.modify(
                customer.id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            user.profile.default_payment_method_id = payment_method_id
            user.profile.save(update_fields=['default_payment_method_id'])

        # Sync to our PaymentMethod model
        from marketplace.models import PaymentMethod
        PaymentMethod.objects.update_or_create(
            user=user,
            stripe_payment_method_id=pm.id,
            defaults={
                'card_brand': pm.card.brand,
                'card_last4': pm.card.last4,
                'card_exp_month': pm.card.exp_month,
                'card_exp_year': pm.card.exp_year,
                'is_default': set_default,
            }
        )

        # If setting as default, unset others
        if set_default:
            PaymentMethod.objects.filter(user=user).exclude(
                stripe_payment_method_id=pm.id
            ).update(is_default=False)

        return pm

    @staticmethod
    def detach_payment_method(payment_method_id):
        """Remove a saved payment method"""
        result = stripe.PaymentMethod.detach(payment_method_id)

        # Remove from our database
        from marketplace.models import PaymentMethod
        PaymentMethod.objects.filter(stripe_payment_method_id=payment_method_id).delete()

        return result

    @staticmethod
    def create_setup_intent(user):
        """Create SetupIntent for saving card without payment"""
        customer = StripeService.get_or_create_customer(user)
        return stripe.SetupIntent.create(
            customer=customer.id,
            payment_method_types=['card'],
            metadata={'user_id': user.id}
        )

    @staticmethod
    def create_payment_intent_for_amount(amount, user, seller, item_price=None, metadata=None):
        """Create a PaymentIntent for a one-off amount (API checkout flow)."""
        customer = StripeService.get_or_create_customer(user)
        seller_profile = seller.profile

        if metadata is None:
            metadata = {}

        total_cents = int(amount * 100)
        fee_base = item_price if item_price is not None else amount

        platform_fee = StripeService.calculate_platform_fee(fee_base, seller)
        platform_fee_cents = int(platform_fee * 100)

        params = {
            'amount': total_cents,
            'currency': 'usd',
            'customer': customer.id,
            'metadata': {
                'buyer_id': user.id,
                'seller_id': seller.id,
                **metadata,
            },
            'automatic_payment_methods': {'enabled': True},
        }

        if seller_profile.stripe_account_id and seller_profile.stripe_charges_enabled:
            params['transfer_data'] = {
                'destination': seller_profile.stripe_account_id,
            }
            params['application_fee_amount'] = platform_fee_cents

        return stripe.PaymentIntent.create(**params)
