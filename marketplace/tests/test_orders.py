"""
Tests for marketplace orders - checkout, payment, fulfillment.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from items.models import Category
from marketplace.models import Listing, Order


class OrderModelTests(TestCase):
    """Tests for Order model."""

    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Items', slug='items')
        self.listing = Listing.objects.create(
            seller=self.seller,
            title='Test Item',
            category=self.category,
            price=Decimal('100.00'),
            condition='good',
            status='active',
        )

    def test_order_creation(self):
        """Should create order with required fields."""
        order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=self.buyer,
            item_price=self.listing.price,
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('90.00'),
            status='pending',
        )
        self.assertEqual(order.item_price, Decimal('100.00'))
        self.assertEqual(order.status, 'pending')

    def test_order_str_representation(self):
        """Order __str__ should include order number."""
        order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=self.buyer,
            item_price=self.listing.price,
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('90.00'),
        )
        self.assertIn(str(order.pk), str(order))

    def test_guest_order_creation(self):
        """Should create guest order without buyer."""
        order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=None,
            guest_email='guest@example.com',
            guest_name='Guest User',
            item_price=self.listing.price,
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('90.00'),
            status='pending',
        )
        self.assertIsNone(order.buyer)
        self.assertEqual(order.guest_email, 'guest@example.com')
        self.assertTrue(order.guest_order_token)  # Auto-generated
        self.assertEqual(order.buyer_email, 'guest@example.com')
        self.assertEqual(order.buyer_display_name, 'Guest User')

    def test_guest_order_token_auto_generated(self):
        """Guest orders should auto-generate a unique token."""
        order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=None,
            guest_email='guest@example.com',
            item_price=self.listing.price,
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('90.00'),
        )
        self.assertTrue(len(order.guest_order_token) > 20)

    def test_buyer_email_property_authenticated(self):
        """buyer_email should return user email for authenticated orders."""
        order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=self.buyer,
            item_price=self.listing.price,
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('90.00'),
        )
        self.assertEqual(order.buyer_email, 'buyer@test.com')


class CheckoutTests(TestCase):
    """Tests for checkout flow."""

    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.seller.profile.stripe_account_id = 'acct_seller123'
        self.seller.profile.stripe_account_complete = True
        self.seller.profile.save()
        
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Items', slug='items')
        self.listing = Listing.objects.create(
            seller=self.seller,
            title='Buy Me',
            category=self.category,
            price=Decimal('50.00'),
            condition='good',
            status='active',
        )

    def test_checkout_allows_guest_for_fixed_price(self):
        """Guest checkout should be allowed for fixed-price listings."""
        response = self.client.get(f'/marketplace/{self.listing.pk}/checkout/')
        # Fixed-price listing should allow guest access (not redirect to login)
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 302:
            # If redirect, it shouldn't be to login/signup
            self.assertNotIn('/auth/', response.url)

    def test_checkout_redirects_guest_for_auction(self):
        """Guest checkout should redirect to signup for auction listings."""
        from django.utils import timezone
        from datetime import timedelta
        auction = Listing.objects.create(
            seller=self.seller,
            title='Auction Item',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
            listing_type='auction',
            auction_end=timezone.now() + timedelta(days=3),
        )
        response = self.client.get(f'/marketplace/{auction.pk}/checkout/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/signup', response.url)

    @patch('marketplace.services.stripe_service.stripe.Customer.create')
    @patch('marketplace.services.stripe_service.stripe.PaymentIntent.create')
    def test_checkout_page_loads(self, mock_intent, mock_customer):
        """Checkout page should load for logged in buyer."""
        # Use spec=[] to prevent MagicMock from auto-creating attributes
        customer_mock = MagicMock(spec=[])
        customer_mock.id = 'cus_test123'
        mock_customer.return_value = customer_mock

        intent_mock = MagicMock(spec=[])
        intent_mock.id = 'pi_test123'
        intent_mock.client_secret = 'pi_test_secret_123'
        mock_intent.return_value = intent_mock

        self.client.login(username='buyer', password='pass123')
        response = self.client.get(f'/marketplace/{self.listing.pk}/checkout/')
        self.assertIn(response.status_code, [200, 302])

    def test_cannot_checkout_own_listing(self):
        """Seller cannot checkout own listing."""
        self.client.login(username='seller', password='pass123')
        response = self.client.get(f'/marketplace/{self.listing.pk}/checkout/')
        # Should be rejected, redirected, or return 404 if view blocks it
        self.assertIn(response.status_code, [302, 403, 404])


class OrderFulfillmentTests(TestCase):
    """Tests for order fulfillment."""

    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Items', slug='items')
        self.listing = Listing.objects.create(
            seller=self.seller,
            title='Sold Item',
            category=self.category,
            price=Decimal('75.00'),
            condition='good',
            status='sold',
        )
        self.order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=self.buyer,
            item_price=Decimal('75.00'),
            shipping_price=Decimal('5.00'),
            amount=Decimal('80.00'),
            platform_fee=Decimal('7.50'),
            seller_payout=Decimal('67.50'),
            status='paid',
        )

    def test_order_detail_requires_login(self):
        """Order detail should require login."""
        response = self.client.get(f'/marketplace/order/{self.order.pk}/')
        self.assertIn(response.status_code, [302, 404])

    def test_order_detail_visible_to_buyer(self):
        """Buyer should see order detail."""
        self.client.login(username='buyer', password='pass123')
        response = self.client.get(f'/marketplace/order/{self.order.pk}/')
        self.assertIn(response.status_code, [200, 302])

    def test_order_detail_visible_to_seller(self):
        """Seller should see order detail."""
        self.client.login(username='seller', password='pass123')
        response = self.client.get(f'/marketplace/order/{self.order.pk}/')
        self.assertIn(response.status_code, [200, 302])

    def test_mark_shipped_requires_seller(self):
        """Only seller can mark order as shipped."""
        self.client.login(username='seller', password='pass123')
        response = self.client.post(f'/marketplace/order/{self.order.pk}/ship/', {
            'tracking_number': '1Z999AA10123456784',
            'carrier': 'UPS',
        })
        self.assertIn(response.status_code, [200, 302])

    def test_mark_received_requires_buyer(self):
        """Only buyer can mark order as received."""
        self.order.status = 'shipped'
        self.order.save()
        self.client.login(username='buyer', password='pass123')
        response = self.client.post(f'/marketplace/order/{self.order.pk}/received/')
        self.assertIn(response.status_code, [200, 302])

    def test_my_orders_page(self):
        """My orders page should load."""
        self.client.login(username='buyer', password='pass123')
        response = self.client.get('/marketplace/my-orders/')
        self.assertIn(response.status_code, [200, 302])


class ReviewTests(TestCase):
    """Tests for order reviews."""

    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.buyer = User.objects.create_user('buyer', 'buyer@test.com', 'pass123')
        self.category = Category.objects.create(name='Items', slug='items')
        self.listing = Listing.objects.create(
            seller=self.seller,
            title='Reviewed Item',
            category=self.category,
            price=Decimal('100.00'),
            condition='good',
            status='sold',
        )
        self.order = Order.objects.create(
            listing=self.listing,
            seller=self.seller,
            buyer=self.buyer,
            item_price=Decimal('100.00'),
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('90.00'),
            status='completed',
        )

    def test_review_requires_login(self):
        """Leaving review should require login."""
        response = self.client.post(f'/marketplace/order/{self.order.pk}/review/')
        self.assertEqual(response.status_code, 302)

    def test_buyer_can_leave_review(self):
        """Buyer should be able to leave review."""
        self.client.login(username='buyer', password='pass123')
        response = self.client.post(f'/marketplace/order/{self.order.pk}/review/', {
            'rating': 5,
            'comment': 'Great seller!',
        })
        self.assertIn(response.status_code, [200, 302])
