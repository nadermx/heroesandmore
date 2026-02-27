from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User

from marketplace.models import Listing
from marketplace.services.usps_service import USPSService
from marketplace.services.shipping_factory import get_shipping_service
from shipping.models import ShippingProfile
from items.models import Category


@override_settings(
    USPS_CLIENT_ID='test_client_id',
    USPS_CLIENT_SECRET='test_client_secret',
    USPS_BASE_URL='https://apis-tem.usps.com',
    SHIPPING_PROVIDER='usps',
)
class USPSServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards-usps')
        self.profile = ShippingProfile.objects.get(slug='graded-slab')
        self.listing = Listing.objects.create(
            seller=self.user, category=self.category, title='PSA 10 Card',
            description='Graded card', condition='mint', price=Decimal('100.00'),
            shipping_mode='calculated', shipping_profile=self.profile,
        )

    def test_build_parcel_from_profile(self):
        parcel = USPSService.build_parcel(self.listing)
        self.assertEqual(parcel['weight'], 8.0)
        self.assertEqual(parcel['length'], 10.0)
        self.assertEqual(parcel['width'], 7.0)
        self.assertEqual(parcel['height'], 2.0)

    def test_build_parcel_with_overrides(self):
        self.listing.weight_oz = Decimal('12')
        self.listing.length_in = Decimal('11')
        self.listing.save()
        parcel = USPSService.build_parcel(self.listing)
        self.assertEqual(parcel['weight'], 12.0)
        self.assertEqual(parcel['length'], 11.0)
        self.assertEqual(parcel['width'], 7.0)

    def test_build_customs_info(self):
        customs = USPSService.build_customs_info(self.listing, 100.00)
        self.assertEqual(customs['contents_type'], 'merchandise')
        self.assertTrue(customs['customs_certify'])
        self.assertEqual(len(customs['customs_items']), 1)
        self.assertEqual(customs['customs_items'][0]['value'], 100.00)

    @patch('marketplace.services.usps_service.requests.post')
    def test_get_token(self, mock_post):
        from django.core.cache import cache
        cache.delete(USPSService.TOKEN_CACHE_KEY)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'access_token': 'test_token_abc',
            'expires_in': 3600,
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        token = USPSService._get_token()
        self.assertEqual(token, 'test_token_abc')
        mock_post.assert_called_once()

    @patch('marketplace.services.usps_service.USPSService._make_request')
    def test_verify_address_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'address': {
                'streetAddress': '123 MAIN ST',
                'secondaryAddress': '',
                'city': 'SPRINGFIELD',
                'state': 'IL',
                'ZIPCode': '62701',
            }
        }
        mock_request.return_value = mock_resp

        result = USPSService.verify_address({
            'name': 'John Doe',
            'street1': '123 Main St',
            'city': 'Springfield',
            'state': 'IL',
            'zip': '62701',
            'country': 'US',
        })

        self.assertTrue(result['verified'])
        self.assertEqual(result['address']['street1'], '123 MAIN ST')
        self.assertEqual(result['address']['city'], 'SPRINGFIELD')
        self.assertTrue(result['easypost_id'].startswith('usps_addr_'))

    @patch('marketplace.services.usps_service.USPSService._make_request')
    def test_verify_address_failure(self, mock_request):
        mock_request.side_effect = Exception("Address not found")

        result = USPSService.verify_address({
            'name': 'Test',
            'street1': 'Bad Address',
            'city': 'Nowhere',
            'state': 'XX',
            'zip': '00000',
            'country': 'US',
        })

        self.assertFalse(result['verified'])
        self.assertTrue(len(result['errors']) > 0)

    @patch('marketplace.services.usps_service.USPSService._make_request')
    def test_get_rates_success(self, mock_request):
        mock_resp = MagicMock()
        # Simulate different responses for each mail class
        def side_effect(method, path, **kwargs):
            mail_class = kwargs.get('json', {}).get('mailClass', '')
            resp = MagicMock()
            prices = {
                'GROUND_ADVANTAGE': '5.50',
                'PRIORITY_MAIL': '8.75',
                'PRIORITY_MAIL_EXPRESS': '26.50',
            }
            resp.json.return_value = {'totalBasePrice': prices.get(mail_class, '10.00')}
            return resp

        mock_request.side_effect = side_effect

        rates = USPSService.get_rates(
            {'zip': '10001'},
            {'zip': '90210'},
            {'weight': 8, 'length': 10, 'width': 7, 'height': 2},
        )

        self.assertEqual(len(rates), 3)
        self.assertEqual(rates[0]['carrier'], 'USPS')
        # Sorted by price ascending
        self.assertLessEqual(rates[0]['rate'], rates[1]['rate'])
        self.assertLessEqual(rates[1]['rate'], rates[2]['rate'])

    @patch('marketplace.services.usps_service.USPSService._make_request')
    def test_get_rates_partial_failure(self, mock_request):
        """If one mail class fails, others should still return."""
        call_count = [0]

        def side_effect(method, path, **kwargs):
            call_count[0] += 1
            mail_class = kwargs.get('json', {}).get('mailClass', '')
            if mail_class == 'PRIORITY_MAIL_EXPRESS':
                raise Exception("Not available")
            resp = MagicMock()
            resp.json.return_value = {'totalBasePrice': '5.00'}
            return resp

        mock_request.side_effect = side_effect

        rates = USPSService.get_rates(
            {'zip': '10001'},
            {'zip': '90210'},
            {'weight': 8, 'length': 10, 'width': 7, 'height': 2},
        )

        self.assertEqual(len(rates), 2)

    @patch('marketplace.services.usps_service.USPSService._make_request')
    def test_get_tracking_delivered(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'statusCategory': 'Delivered',
            'expectedDeliveryDate': '2026-03-01',
            'trackingEvents': [
                {
                    'eventType': 'Delivered',
                    'eventDescription': 'Delivered, In/At Mailbox',
                    'eventTimestamp': '2026-02-27T14:30:00Z',
                    'eventCity': 'Springfield',
                    'eventState': 'IL',
                },
            ],
        }
        mock_request.return_value = mock_resp

        result = USPSService.get_tracking('9400111899223456789012')
        self.assertEqual(result['status'], 'delivered')
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['events'][0]['city'], 'Springfield')

    def test_process_tracking_webhook_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            USPSService.process_tracking_webhook({})

    def test_refund_label_manual(self):
        result = USPSService.refund_label('usps_shp_test')
        self.assertEqual(result['status'], 'manual_refund_required')


class ShippingFactoryTests(TestCase):
    @override_settings(SHIPPING_PROVIDER='usps')
    def test_factory_returns_usps(self):
        service = get_shipping_service()
        self.assertEqual(service, USPSService)

    @override_settings(SHIPPING_PROVIDER='easypost')
    def test_factory_returns_easypost(self):
        from marketplace.services.easypost_service import EasyPostService
        service = get_shipping_service()
        self.assertEqual(service, EasyPostService)
