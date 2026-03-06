import logging
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('marketplace')

# PayPal API base URLs
PAYPAL_API_BASE = 'https://api-m.paypal.com'
PAYPAL_API_SANDBOX = 'https://api-m.sandbox.paypal.com'


class PayPalService:
    """PayPal REST API v2 integration for orders and payouts."""

    _access_token = None
    _token_expires = None

    @classmethod
    def _get_base_url(cls):
        return PAYPAL_API_SANDBOX if getattr(settings, 'PAYPAL_SANDBOX', False) else PAYPAL_API_BASE

    @classmethod
    def _get_access_token(cls):
        """Get OAuth2 access token, caching until expiry."""
        now = timezone.now()
        if cls._access_token and cls._token_expires and now < cls._token_expires:
            return cls._access_token

        url = f"{cls._get_base_url()}/v1/oauth2/token"
        resp = requests.post(
            url,
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            headers={'Accept': 'application/json'},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        cls._access_token = data['access_token']
        # Expire 5 minutes early to be safe
        cls._token_expires = now + timezone.timedelta(seconds=data.get('expires_in', 3600) - 300)
        return cls._access_token

    @classmethod
    def _headers(cls):
        return {
            'Authorization': f'Bearer {cls._get_access_token()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    @classmethod
    def create_order(cls, order):
        """Create a PayPal order for checkout.

        Args:
            order: marketplace.Order instance

        Returns:
            dict with 'id' (PayPal order ID) and 'status'
        """
        from marketplace.services.stripe_service import StripeService

        total = str(order.amount.quantize(Decimal('0.01')))
        item_price = str(order.item_price.quantize(Decimal('0.01')))
        shipping = str(order.shipping_price.quantize(Decimal('0.01')))

        # Calculate platform fee
        platform_fee = StripeService.calculate_platform_fee(order.item_price, order.seller)
        platform_fee_str = str(platform_fee.quantize(Decimal('0.01')))

        purchase_unit = {
            'reference_id': str(order.id),
            'description': f"Order #{order.id} - {order.listing.title[:100] if order.listing else 'Order'}",
            'custom_id': str(order.id),
            'amount': {
                'currency_code': 'USD',
                'value': total,
                'breakdown': {
                    'item_total': {'currency_code': 'USD', 'value': item_price},
                    'shipping': {'currency_code': 'USD', 'value': shipping},
                }
            },
            'items': [{
                'name': order.listing.title[:127] if order.listing else 'Item',
                'quantity': str(order.quantity),
                'unit_amount': {
                    'currency_code': 'USD',
                    'value': str((order.item_price / order.quantity).quantize(Decimal('0.01'))),
                },
                'category': 'PHYSICAL_GOODS',
            }],
            # Let PayPal collect shipping address from buyer's account
            'shipping': {
                'options': [{
                    'id': 'default',
                    'label': 'Shipping',
                    'selected': True,
                    'amount': {'currency_code': 'USD', 'value': shipping},
                }],
            },
        }

        # If we already have a shipping address, pass it to PayPal as the default
        if order.shipping_address_obj:
            addr = order.shipping_address_obj
            purchase_unit['shipping']['name'] = {
                'full_name': addr.name,
            }
            purchase_unit['shipping']['address'] = {
                'address_line_1': addr.street1,
                'address_line_2': addr.street2 or '',
                'admin_area_2': addr.city,
                'admin_area_1': addr.state,
                'postal_code': addr.zip_code,
                'country_code': addr.country or 'US',
            }

        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [purchase_unit],
            # application_context for shipping preference
            'application_context': {
                'brand_name': 'HeroesAndMore',
                'landing_page': 'LOGIN',
                'user_action': 'PAY_NOW',
                'shipping_preference': 'GET_FROM_FILE',  # PayPal shows buyer's saved addresses
                'return_url': f"{settings.SITE_URL}/marketplace/order/{order.id}/complete/",
                'cancel_url': f"{settings.SITE_URL}/marketplace/{order.listing_id}/checkout/" if order.listing_id else f"{settings.SITE_URL}/marketplace/",
            },
        }

        url = f"{cls._get_base_url()}/v2/checkout/orders"
        resp = requests.post(url, json=payload, headers=cls._headers(), timeout=30)

        if resp.status_code not in (200, 201):
            logger.error(f"PayPal create order failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()

        data = resp.json()

        # Store PayPal order ID on our order
        order.paypal_order_id = data['id']
        order.platform_fee = platform_fee
        order.seller_payout = order.item_price - platform_fee
        order.payment_method = 'paypal'
        order.save(update_fields=['paypal_order_id', 'platform_fee', 'seller_payout', 'payment_method'])

        logger.info(f"Created PayPal order {data['id']} for order #{order.id}")
        return data

    @classmethod
    def capture_order(cls, paypal_order_id):
        """Capture an approved PayPal order.

        Returns:
            dict with capture details
        """
        url = f"{cls._get_base_url()}/v2/checkout/orders/{paypal_order_id}/capture"
        resp = requests.post(url, json={}, headers=cls._headers(), timeout=30)

        if resp.status_code not in (200, 201):
            logger.error(f"PayPal capture failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()

        data = resp.json()
        logger.info(f"Captured PayPal order {paypal_order_id}: status={data.get('status')}")
        return data

    @staticmethod
    def extract_shipping_address(paypal_data):
        """Extract shipping address from PayPal order/capture response.

        Returns:
            dict with name, street1, street2, city, state, zip_code, country
            or None if no address found
        """
        try:
            shipping = paypal_data['purchase_units'][0].get('shipping', {})
            address = shipping.get('address', {})
            name_obj = shipping.get('name', {})

            if not address.get('admin_area_2'):  # city is required minimum
                return None

            return {
                'name': name_obj.get('full_name', ''),
                'street1': address.get('address_line_1', ''),
                'street2': address.get('address_line_2', ''),
                'city': address.get('admin_area_2', ''),
                'state': address.get('admin_area_1', ''),
                'zip_code': address.get('postal_code', ''),
                'country': address.get('country_code', 'US'),
            }
        except (KeyError, IndexError):
            return None

    @staticmethod
    def extract_payer_info(paypal_data):
        """Extract buyer email and name from PayPal response.

        Returns:
            dict with email, first_name, last_name, full_name
            or None if not found
        """
        try:
            payer = paypal_data.get('payer', {})
            name = payer.get('name', {})
            return {
                'email': payer.get('email_address', ''),
                'first_name': name.get('given_name', ''),
                'last_name': name.get('surname', ''),
                'full_name': f"{name.get('given_name', '')} {name.get('surname', '')}".strip(),
            }
        except (KeyError, AttributeError):
            return None

    @classmethod
    def get_order_details(cls, paypal_order_id):
        """Retrieve PayPal order details."""
        url = f"{cls._get_base_url()}/v2/checkout/orders/{paypal_order_id}"
        resp = requests.get(url, headers=cls._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def refund_capture(cls, capture_id, amount=None):
        """Refund a captured PayPal payment.

        Args:
            capture_id: PayPal capture ID
            amount: Decimal amount for partial refund, None for full
        """
        url = f"{cls._get_base_url()}/v2/payments/captures/{capture_id}/refund"
        payload = {}
        if amount is not None:
            payload['amount'] = {
                'currency_code': 'USD',
                'value': str(amount.quantize(Decimal('0.01'))),
            }

        resp = requests.post(url, json=payload, headers=cls._headers(), timeout=30)

        if resp.status_code not in (200, 201):
            logger.error(f"PayPal refund failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()

        data = resp.json()
        logger.info(f"PayPal refund {data.get('id')} for capture {capture_id}: status={data.get('status')}")
        return data

    @classmethod
    def send_payout(cls, email, amount, order_id=None, note=None):
        """Send a payout to a seller's PayPal email.

        Args:
            email: Seller's PayPal email address
            amount: Decimal payout amount
            order_id: Optional order ID for reference
            note: Optional note to seller

        Returns:
            dict with payout batch details
        """
        import uuid
        batch_id = f"order-{order_id}-{uuid.uuid4().hex[:8]}" if order_id else f"payout-{uuid.uuid4().hex[:12]}"

        payload = {
            'sender_batch_header': {
                'sender_batch_id': batch_id,
                'email_subject': 'You have a payout from HeroesAndMore',
                'email_message': note or 'Your sale payout has been sent.',
            },
            'items': [{
                'recipient_type': 'EMAIL',
                'amount': {
                    'value': str(amount.quantize(Decimal('0.01'))),
                    'currency': 'USD',
                },
                'receiver': email,
                'note': note or f'Payout for order #{order_id}' if order_id else 'HeroesAndMore payout',
                'sender_item_id': str(order_id) if order_id else batch_id,
            }],
        }

        url = f"{cls._get_base_url()}/v1/payments/payouts"
        resp = requests.post(url, json=payload, headers=cls._headers(), timeout=30)

        if resp.status_code not in (200, 201):
            logger.error(f"PayPal payout failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()

        data = resp.json()
        logger.info(f"PayPal payout batch {batch_id} sent to {email}: ${amount}")
        return data

    @classmethod
    def verify_webhook_signature(cls, headers, body):
        """Verify PayPal webhook signature.

        Args:
            headers: Request headers dict
            body: Raw request body string

        Returns:
            bool: True if signature is valid
        """
        webhook_id = getattr(settings, 'PAYPAL_WEBHOOK_ID', '')
        if not webhook_id:
            logger.warning("PAYPAL_WEBHOOK_ID not configured, skipping verification")
            return True

        url = f"{cls._get_base_url()}/v1/notifications/verify-webhook-signature"
        payload = {
            'auth_algo': headers.get('PAYPAL-AUTH-ALGO', ''),
            'cert_url': headers.get('PAYPAL-CERT-URL', ''),
            'transmission_id': headers.get('PAYPAL-TRANSMISSION-ID', ''),
            'transmission_sig': headers.get('PAYPAL-TRANSMISSION-SIG', ''),
            'transmission_time': headers.get('PAYPAL-TRANSMISSION-TIME', ''),
            'webhook_id': webhook_id,
            'webhook_event': body if isinstance(body, dict) else {},
        }

        try:
            resp = requests.post(url, json=payload, headers=cls._headers(), timeout=15)
            resp.raise_for_status()
            return resp.json().get('verification_status') == 'SUCCESS'
        except Exception as e:
            logger.error(f"PayPal webhook verification failed: {e}")
            return False
