from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from marketplace.models import Listing, Order
from shipping.models import Address, ShippingProfile
from items.models import Category


class CheckoutShippingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_flat_rate_checkout_unchanged(self):
        """Flat rate listings should work exactly as before"""
        listing = Listing.objects.create(
            seller=self.seller, category=self.category, title='Test Card',
            description='Test', condition='mint', price=Decimal('25.00'),
            shipping_mode='flat', shipping_price=Decimal('5.00'),
            status='active',
        )
        self.client.login(username='buyer', password='pass123')
        resp = self.client.get(reverse('marketplace:checkout', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['use_calculated_shipping'])

    def test_calculated_shipping_checkout(self):
        """Calculated shipping should show rate shopping UI"""
        listing = Listing.objects.create(
            seller=self.seller, category=self.category, title='Graded Slab',
            description='Test', condition='mint', price=Decimal('100.00'),
            shipping_mode='calculated', status='active',
        )
        self.client.login(username='buyer', password='pass123')
        resp = self.client.get(reverse('marketplace:checkout', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['use_calculated_shipping'])

    def test_free_shipping_checkout(self):
        """Free shipping should show $0"""
        listing = Listing.objects.create(
            seller=self.seller, category=self.category, title='Free Ship Card',
            description='Test', condition='mint', price=Decimal('10.00'),
            shipping_mode='free', status='active',
        )
        self.client.login(username='buyer', password='pass123')
        resp = self.client.get(reverse('marketplace:checkout', args=[listing.pk]))
        self.assertEqual(resp.status_code, 200)
        order = resp.context['order']
        self.assertEqual(order.shipping_price, Decimal('0'))


class ValidateAddressViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('marketplace.services.easypost_service.EasyPostService.verify_address')
    def test_validate_address(self, mock_verify):
        mock_verify.return_value = {
            'verified': True,
            'easypost_id': 'adr_123',
            'address': {
                'name': 'John Doe',
                'street1': '123 MAIN ST',
                'city': 'SPRINGFIELD',
                'state': 'IL',
                'zip': '62701',
                'country': 'US',
            },
            'errors': [],
        }
        resp = self.client.post(reverse('marketplace:validate_address'), {
            'name': 'John Doe',
            'street1': '123 Main St',
            'city': 'Springfield',
            'state': 'IL',
            'zip': '62701',
            'country': 'US',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['verified'])

    def test_validate_address_missing_fields(self):
        resp = self.client.post(reverse('marketplace:validate_address'), {
            'name': 'John',
            'street1': '',
            'city': '',
            'state': '',
            'zip': '',
        })
        self.assertEqual(resp.status_code, 400)


class SelectRateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller, category=self.category, title='Test',
            description='Test', condition='mint', price=Decimal('50.00'),
            shipping_mode='calculated', status='active',
        )

    def test_select_rate_updates_order(self):
        self.client.login(username='buyer', password='pass123')
        # Create order first via checkout
        self.client.get(reverse('marketplace:checkout', args=[self.listing.pk]))

        order = Order.objects.get(listing=self.listing, buyer=self.buyer)
        self.assertEqual(order.shipping_mode, 'calculated')
        self.assertEqual(order.shipping_price, Decimal('0'))

        resp = self.client.post(reverse('marketplace:select_shipping_rate', args=[order.pk]), {
            'rate_id': 'rate_123',
            'shipment_id': 'shp_123',
            'rate': '7.50',
            'carrier': 'USPS',
            'service': 'Priority',
        })
        self.assertEqual(resp.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.shipping_price, Decimal('7.50'))
        self.assertEqual(order.amount, Decimal('57.50'))
        self.assertEqual(order.selected_carrier, 'USPS')


class ShipFromAddressTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')

    def test_get_ship_from_page(self):
        self.client.login(username='seller', password='pass123')
        resp = self.client.get(reverse('seller_tools:ship_from_address'))
        self.assertEqual(resp.status_code, 200)

    def test_save_ship_from_address(self):
        self.client.login(username='seller', password='pass123')
        resp = self.client.post(reverse('seller_tools:ship_from_address'), {
            'name': 'Test Seller',
            'street1': '100 Seller Blvd',
            'city': 'Austin',
            'state': 'TX',
            'zip_code': '78701',
            'country': 'US',
        })
        self.assertEqual(resp.status_code, 302)

        self.user.profile.refresh_from_db()
        addr = self.user.profile.default_ship_from
        self.assertIsNotNone(addr)
        self.assertEqual(addr.city, 'Austin')
