from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User

from marketplace.models import Listing, Order
from marketplace.services.easypost_service import EasyPostService
from marketplace.services.stripe_service import StripeService
from shipping.models import Address, ShippingProfile, ShippingLabel
from items.models import Category


class EasyPostServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.profile = ShippingProfile.objects.get(slug='graded-slab')
        self.listing = Listing.objects.create(
            seller=self.user, category=self.category, title='PSA 10 Card',
            description='Graded card', condition='mint', price=Decimal('100.00'),
            shipping_mode='calculated', shipping_profile=self.profile,
        )

    def test_build_parcel_from_profile(self):
        parcel = EasyPostService.build_parcel(self.listing)
        self.assertEqual(parcel['weight'], 8.0)
        self.assertEqual(parcel['length'], 10.0)
        self.assertEqual(parcel['width'], 7.0)
        self.assertEqual(parcel['height'], 2.0)

    def test_build_parcel_with_overrides(self):
        self.listing.weight_oz = Decimal('12')
        self.listing.length_in = Decimal('11')
        self.listing.save()
        parcel = EasyPostService.build_parcel(self.listing)
        self.assertEqual(parcel['weight'], 12.0)
        self.assertEqual(parcel['length'], 11.0)
        # Width/height from profile
        self.assertEqual(parcel['width'], 7.0)

    def test_build_parcel_no_profile(self):
        self.listing.shipping_profile = None
        self.listing.save()
        parcel = EasyPostService.build_parcel(self.listing)
        # Should use defaults
        self.assertEqual(parcel['weight'], 2)  # default

    def test_build_customs_info(self):
        customs = EasyPostService.build_customs_info(self.listing, 100.00)
        self.assertEqual(customs['contents_type'], 'merchandise')
        self.assertTrue(customs['customs_certify'])
        self.assertEqual(len(customs['customs_items']), 1)
        self.assertEqual(customs['customs_items'][0]['value'], 100.00)

    @patch('marketplace.services.easypost_service.EasyPostService.get_client')
    def test_verify_address_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_address = MagicMock()
        mock_address.id = 'adr_123'

        mock_verified = MagicMock()
        mock_verified.id = 'adr_123'
        mock_verified.name = 'John Doe'
        mock_verified.company = None
        mock_verified.street1 = '123 MAIN ST'
        mock_verified.street2 = ''
        mock_verified.city = 'SPRINGFIELD'
        mock_verified.state = 'IL'
        mock_verified.zip = '62701'
        mock_verified.country = 'US'
        mock_verified.phone = ''

        mock_client.address.create.return_value = mock_address
        mock_client.address.verify.return_value = mock_verified

        result = EasyPostService.verify_address({
            'name': 'John Doe',
            'street1': '123 Main St',
            'city': 'Springfield',
            'state': 'IL',
            'zip': '62701',
            'country': 'US',
        })

        self.assertTrue(result['verified'])
        self.assertEqual(result['easypost_id'], 'adr_123')

    @patch('marketplace.services.easypost_service.EasyPostService.get_client')
    def test_verify_address_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.address.create.side_effect = Exception("Bad address")

        result = EasyPostService.verify_address({
            'name': 'Test',
            'street1': 'Bad Address',
            'city': 'Nowhere',
            'state': 'XX',
            'zip': '00000',
            'country': 'US',
        })

        self.assertFalse(result['verified'])
        self.assertTrue(len(result['errors']) > 0)

    def test_process_tracking_webhook_delivered(self):
        """Test that delivered tracking updates order status"""
        from django.utils import timezone

        order = Order.objects.create(
            listing=self.listing, buyer=self.buyer, seller=self.user,
            quantity=1, item_price=Decimal('100'), shipping_price=Decimal('5'),
            amount=Decimal('105'), platform_fee=Decimal('10'),
            seller_payout=Decimal('90'), shipping_address='Test',
            tracking_number='TRACK123', tracking_carrier='USPS',
            status='shipped', shipped_at=timezone.now(),
        )

        EasyPostService.process_tracking_webhook({
            'result': {
                'tracking_code': 'TRACK123',
                'status': 'delivered',
            }
        })

        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertIsNotNone(order.delivered_at)

    def test_process_tracking_webhook_no_backwards(self):
        """Status should never go backwards"""
        from django.utils import timezone

        order = Order.objects.create(
            listing=self.listing, buyer=self.buyer, seller=self.user,
            quantity=1, item_price=Decimal('100'), shipping_price=Decimal('5'),
            amount=Decimal('105'), platform_fee=Decimal('10'),
            seller_payout=Decimal('90'), shipping_address='Test',
            tracking_number='TRACK456', tracking_carrier='USPS',
            status='delivered', shipped_at=timezone.now(), delivered_at=timezone.now(),
        )

        EasyPostService.process_tracking_webhook({
            'result': {
                'tracking_code': 'TRACK456',
                'status': 'in_transit',
            }
        })

        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')  # unchanged


class PlatformFeeTests(TestCase):
    """Test that the fee structure includes Stripe fee + shipping label fee + commission %"""

    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')

    def test_flat_fee_amount(self):
        """Flat fee should be $0.29 Stripe + $0.05 label = $0.34"""
        self.assertEqual(StripeService.PLATFORM_FLAT_FEE, Decimal('0.34'))

    def test_calculate_platform_fee(self):
        """Fee = $0.34 flat + (price * commission rate)"""
        price = Decimal('100.00')
        fee = StripeService.calculate_platform_fee(price, self.user)
        # Default starter commission is 12.95%
        expected = Decimal('0.34') + price * Decimal('0.1295')
        self.assertEqual(fee, expected.quantize(Decimal('0.01')))

    def test_platform_account_gets_full_price(self):
        """Platform accounts keep the full price"""
        self.user.profile.is_platform_account = True
        self.user.profile.save()
        price = Decimal('50.00')
        fee = StripeService.calculate_platform_fee(price, self.user)
        self.assertEqual(fee, price)
