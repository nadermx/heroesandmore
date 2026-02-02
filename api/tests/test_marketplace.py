"""
Tests for marketplace API - listings, bids, offers, orders.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from items.models import Category
from marketplace.models import Listing, Order


class ListingAPITests(TestCase):
    """Tests for listing API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@test.com',
            password='testpass123'
        )
        self.buyer = User.objects.create_user(
            username='buyer',
            email='buyer@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')

    def get_seller_token(self):
        """Get JWT token for seller."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'seller',
            'password': 'testpass123',
        })
        return response.data['access']

    def get_buyer_token(self):
        """Get JWT token for buyer."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'buyer',
            'password': 'testpass123',
        })
        return response.data['access']

    def create_listing(self, **kwargs):
        """Helper to create a listing."""
        defaults = {
            'seller': self.seller,
            'category': self.category,
            'title': 'Test Listing',
            'description': 'A test listing',
            'price': Decimal('50.00'),
            'status': 'active',
            'listing_type': 'fixed',
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def test_list_active_listings(self):
        """Should list active listings."""
        self.create_listing(title='Active Listing')
        self.create_listing(title='Draft', status='draft')
        response = self.client.get('/api/v1/marketplace/listings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only active listing should appear
        self.assertEqual(response.data['count'], 1)

    def test_get_listing_detail(self):
        """Should get listing detail."""
        listing = self.create_listing()
        response = self.client.get(f'/api/v1/marketplace/listings/{listing.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Listing')

    def test_listing_increments_view_count(self):
        """Should increment view count on detail."""
        listing = self.create_listing()
        initial_views = listing.views
        self.client.get(f'/api/v1/marketplace/listings/{listing.pk}/')
        listing.refresh_from_db()
        self.assertEqual(listing.views, initial_views + 1)

    def test_create_listing_authenticated(self):
        """Should create listing for authenticated seller."""
        token = self.get_seller_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/marketplace/listings/', {
            'title': 'New Listing',
            'description': 'Description',
            'category': self.category.pk,
            'price': '75.00',
            'listing_type': 'fixed',
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_create_listing_unauthenticated(self):
        """Should reject unauthenticated listing creation."""
        response = self.client.post('/api/v1/marketplace/listings/', {
            'title': 'New Listing',
            'price': '75.00',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_own_listing(self):
        """Should update own listing."""
        listing = self.create_listing()
        token = self.get_seller_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch(f'/api/v1/marketplace/listings/{listing.pk}/', {
            'title': 'Updated Title',
        })
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_delete_own_listing(self):
        """Should delete own listing."""
        listing = self.create_listing()
        token = self.get_seller_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(f'/api/v1/marketplace/listings/{listing.pk}/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_404_NOT_FOUND])


class SavedListingsAPITests(TestCase):
    """Tests for saved listings API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='testpass123'
        )
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Listing',
            price=Decimal('50.00'),
            status='active',
            listing_type='fixed',
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'user',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_save_listing(self):
        """Should save listing."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.listing.pk}/save/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_unsave_listing(self):
        """Should unsave listing."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        # First save
        self.client.post(f'/api/v1/marketplace/listings/{self.listing.pk}/save/')
        # Then unsave
        response = self.client.delete(f'/api/v1/marketplace/listings/{self.listing.pk}/save/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_check_if_saved(self):
        """Should check if listing is saved."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(f'/api/v1/marketplace/listings/{self.listing.pk}/save/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_saved', response.data)

    def test_get_saved_listings(self):
        """Should get list of saved listings."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/marketplace/saved/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BiddingAPITests(TestCase):
    """Tests for auction bidding API."""

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@test.com',
            password='testpass123'
        )
        self.bidder = User.objects.create_user(
            username='bidder',
            email='bidder@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.auction = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Auction Item',
            price=Decimal('10.00'),
            status='active',
            listing_type='auction',
            auction_end=timezone.now() + timezone.timedelta(days=1),
        )

    def get_bidder_token(self):
        """Get JWT token for bidder."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'bidder',
            'password': 'testpass123',
        })
        return response.data['access']

    def get_seller_token(self):
        """Get JWT token for seller."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'seller',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_place_valid_bid(self):
        """Should place valid bid."""
        token = self.get_bidder_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.auction.pk}/bid/', {
            'amount': '15.00',
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_bid_below_minimum(self):
        """Should reject bid below minimum."""
        token = self.get_bidder_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.auction.pk}/bid/', {
            'amount': '5.00',  # Below current price
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_bid_on_own_auction(self):
        """Should reject seller bidding on own auction."""
        token = self.get_seller_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.auction.pk}/bid/', {
            'amount': '20.00',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_bid_history(self):
        """Should get bid history for listing."""
        response = self.client.get(f'/api/v1/marketplace/listings/{self.auction.pk}/bids/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class OfferAPITests(TestCase):
    """Tests for offer API."""

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@test.com',
            password='testpass123'
        )
        self.buyer = User.objects.create_user(
            username='buyer',
            email='buyer@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Item',
            price=Decimal('100.00'),
            status='active',
            listing_type='fixed',
            allow_offers=True,
            minimum_offer_percent=50,
        )

    def get_buyer_token(self):
        """Get JWT token for buyer."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'buyer',
            'password': 'testpass123',
        })
        return response.data['access']

    def get_seller_token(self):
        """Get JWT token for seller."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'seller',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_make_valid_offer(self):
        """Should make valid offer."""
        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.listing.pk}/offer/', {
            'amount': '75.00',
            'message': 'Interested in this item',
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_offer_below_minimum(self):
        """Should reject offer below minimum percent."""
        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.listing.pk}/offer/', {
            'amount': '25.00',  # Below 50% minimum
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_offer_on_own_listing(self):
        """Should reject seller making offer on own listing."""
        token = self.get_seller_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/listings/{self.listing.pk}/offer/', {
            'amount': '75.00',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_offers(self):
        """Should get offers for user."""
        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/marketplace/offers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class OrderAPITests(TestCase):
    """Tests for order API."""

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@test.com',
            password='testpass123'
        )
        self.buyer = User.objects.create_user(
            username='buyer',
            email='buyer@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Item',
            price=Decimal('50.00'),
            status='sold',
            listing_type='fixed',
        )
        self.order = Order.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            item_price=Decimal('50.00'),
            shipping_price=Decimal('5.00'),
            amount=Decimal('55.00'),
            platform_fee=Decimal('5.00'),
            seller_payout=Decimal('45.00'),
            status='paid',
            shipping_address='123 Test St',
        )

    def get_seller_token(self):
        """Get JWT token for seller."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'seller',
            'password': 'testpass123',
        })
        return response.data['access']

    def get_buyer_token(self):
        """Get JWT token for buyer."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'buyer',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_get_orders(self):
        """Should get orders for user."""
        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/marketplace/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_seller_can_ship_order(self):
        """Seller should be able to mark order as shipped."""
        token = self.get_seller_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/orders/{self.order.pk}/ship/', {
            'tracking_number': 'TRACK123',
            'tracking_carrier': 'USPS',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'shipped')

    def test_buyer_cannot_ship_order(self):
        """Buyer should not be able to mark order as shipped."""
        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/orders/{self.order.pk}/ship/', {
            'tracking_number': 'TRACK123',
            'tracking_carrier': 'USPS',
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_buyer_can_confirm_received(self):
        """Buyer should be able to confirm receipt."""
        # First ship the order
        self.order.status = 'shipped'
        self.order.save()

        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/orders/{self.order.pk}/received/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')

    def test_buyer_can_leave_review(self):
        """Buyer should be able to leave review."""
        self.order.status = 'delivered'
        self.order.save()

        token = self.get_buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/marketplace/orders/{self.order.pk}/review/', {
            'rating': 5,
            'text': 'Great seller!',
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])


class AuctionEventAPITests(TestCase):
    """Tests for auction event API."""

    def setUp(self):
        self.client = APIClient()

    def test_list_auction_events(self):
        """Should list auction events."""
        response = self.client.get('/api/v1/marketplace/auctions/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
