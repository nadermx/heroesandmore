import json
import hmac
import hashlib
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

from marketplace.models import Listing, Order
from items.models import Category


class EasyPostWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller, category=self.category, title='Test',
            description='Test', condition='mint', price=Decimal('50.00'),
            status='active',
        )
        self.order = Order.objects.create(
            listing=self.listing, buyer=self.buyer, seller=self.seller,
            quantity=1, item_price=Decimal('50'), shipping_price=Decimal('5'),
            amount=Decimal('55'), platform_fee=Decimal('5'),
            seller_payout=Decimal('45'), shipping_address='Test Address',
            tracking_number='EP123456', tracking_carrier='USPS',
            status='shipped', shipped_at=timezone.now(),
        )

    @override_settings(EASYPOST_WEBHOOK_SECRET='')
    def test_webhook_tracker_updated_delivered(self):
        payload = json.dumps({
            'description': 'tracker.updated',
            'result': {
                'tracking_code': 'EP123456',
                'status': 'delivered',
            }
        })
        resp = self.client.post(
            reverse('shipping:easypost_webhook'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')

    @override_settings(EASYPOST_WEBHOOK_SECRET='')
    def test_webhook_unknown_tracking(self):
        """Webhook for unknown tracking number should not error"""
        payload = json.dumps({
            'description': 'tracker.updated',
            'result': {
                'tracking_code': 'UNKNOWN999',
                'status': 'delivered',
            }
        })
        resp = self.client.post(
            reverse('shipping:easypost_webhook'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

    @override_settings(EASYPOST_WEBHOOK_SECRET='test-secret')
    def test_webhook_invalid_signature(self):
        payload = json.dumps({'description': 'tracker.updated', 'result': {}})
        resp = self.client.post(
            reverse('shipping:easypost_webhook'),
            data=payload,
            content_type='application/json',
            HTTP_X_HMAC_SIGNATURE='invalid',
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(EASYPOST_WEBHOOK_SECRET='test-secret')
    def test_webhook_valid_signature(self):
        payload = json.dumps({
            'description': 'tracker.updated',
            'result': {
                'tracking_code': 'EP123456',
                'status': 'in_transit',
            }
        })
        sig = hmac.new(
            b'test-secret',
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        resp = self.client.post(
            reverse('shipping:easypost_webhook'),
            data=payload,
            content_type='application/json',
            HTTP_X_HMAC_SIGNATURE=f'hmac-sha256-hex={sig}',
        )
        self.assertEqual(resp.status_code, 200)

    def test_webhook_get_not_allowed(self):
        resp = self.client.get(reverse('shipping:easypost_webhook'))
        self.assertEqual(resp.status_code, 405)
