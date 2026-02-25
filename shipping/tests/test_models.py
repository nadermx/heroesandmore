from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from shipping.models import Address, ShippingProfile, ShippingLabel, ShippingRate
from marketplace.models import Listing, Order
from items.models import Category


class AddressModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')
        self.address = Address.objects.create(
            user=self.user,
            name='John Doe',
            street1='123 Main St',
            street2='Apt 4',
            city='Springfield',
            state='IL',
            zip_code='62701',
            country='US',
        )

    def test_str(self):
        self.assertIn('John Doe', str(self.address))
        self.assertIn('123 Main St', str(self.address))

    def test_formatted(self):
        formatted = self.address.formatted
        self.assertIn('John Doe', formatted)
        self.assertIn('123 Main St', formatted)
        self.assertIn('Apt 4', formatted)
        self.assertIn('Springfield, IL 62701', formatted)
        # US country should not be shown
        self.assertNotIn('US', formatted.split('\n')[-1])

    def test_formatted_international(self):
        self.address.country = 'CA'
        self.address.save()
        formatted = self.address.formatted
        self.assertIn('CA', formatted)

    def test_to_easypost_dict(self):
        d = self.address.to_easypost_dict()
        self.assertEqual(d['name'], 'John Doe')
        self.assertEqual(d['street1'], '123 Main St')
        self.assertEqual(d['zip'], '62701')
        self.assertEqual(d['country'], 'US')

    def test_default_address_uniqueness(self):
        """Only one default address per user"""
        self.address.is_default = True
        self.address.save()

        addr2 = Address.objects.create(
            user=self.user,
            name='Jane Doe',
            street1='456 Oak Ave',
            city='Chicago',
            state='IL',
            zip_code='60601',
            is_default=True,
        )

        self.address.refresh_from_db()
        self.assertFalse(self.address.is_default)
        self.assertTrue(addr2.is_default)


class ShippingProfileTests(TestCase):
    def test_seed_profiles_exist(self):
        """Verify seed profiles were created by migration"""
        profiles = ShippingProfile.objects.all()
        self.assertTrue(profiles.exists())
        slugs = profiles.values_list('slug', flat=True)
        self.assertIn('standard-card', slugs)
        self.assertIn('graded-slab', slugs)
        self.assertIn('figure-toy', slugs)

    def test_standard_card_dimensions(self):
        profile = ShippingProfile.objects.get(slug='standard-card')
        self.assertEqual(profile.weight_oz, Decimal('2.00'))
        self.assertEqual(profile.length_in, Decimal('9.50'))


class ShippingRateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.user, category=self.category, title='Test Card',
            description='A test card', condition='mint', price=Decimal('10.00'),
            shipping_mode='calculated',
        )
        self.address = Address.objects.create(
            name='Buyer', street1='789 Elm', city='NYC', state='NY', zip_code='10001',
        )

    def test_is_expired(self):
        rate = ShippingRate.objects.create(
            listing=self.listing, to_address=self.address,
            easypost_shipment_id='shp_123', easypost_rate_id='rate_123',
            carrier='USPS', service='Priority', rate=Decimal('5.99'),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(rate.is_expired)

    def test_not_expired(self):
        rate = ShippingRate.objects.create(
            listing=self.listing, to_address=self.address,
            easypost_shipment_id='shp_123', easypost_rate_id='rate_123',
            carrier='USPS', service='Priority', rate=Decimal('5.99'),
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        self.assertFalse(rate.is_expired)
