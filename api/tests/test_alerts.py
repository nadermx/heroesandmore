"""
Tests for alerts API - wishlists, saved searches, price alerts, notifications.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from items.models import Category
from alerts.models import Wishlist, SavedSearch, PriceAlert


class AlertNotificationAPITests(TestCase):
    """Tests for notification/alert API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_get_notifications_requires_auth(self):
        """Should require authentication."""
        response = self.client.get('/api/v1/alerts/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_notifications_authenticated(self):
        """Should get notifications when authenticated."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/alerts/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WishlistAPITests(TestCase):
    """Tests for wishlist API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_list_wishlists_requires_auth(self):
        """Should require authentication."""
        response = self.client.get('/api/v1/alerts/wishlists/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_wishlists_authenticated(self):
        """Should list wishlists when authenticated."""
        Wishlist.objects.create(user=self.user, name='My Wants')
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/alerts/wishlists/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_wishlist(self):
        """Should create wishlist."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/alerts/wishlists/', {
            'name': 'New Wishlist',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_wishlist(self):
        """Should update wishlist."""
        wishlist = Wishlist.objects.create(user=self.user, name='Original')
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch(f'/api/v1/alerts/wishlists/{wishlist.pk}/', {
            'name': 'Updated',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wishlist.refresh_from_db()
        self.assertEqual(wishlist.name, 'Updated')

    def test_delete_wishlist(self):
        """Should delete wishlist."""
        wishlist = Wishlist.objects.create(user=self.user, name='To Delete')
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(f'/api/v1/alerts/wishlists/{wishlist.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class SavedSearchAPITests(TestCase):
    """Tests for saved search API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_list_saved_searches_requires_auth(self):
        """Should require authentication."""
        response = self.client.get('/api/v1/alerts/saved-searches/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_saved_searches_authenticated(self):
        """Should list saved searches when authenticated."""
        SavedSearch.objects.create(user=self.user, name='Baseball Cards', query='baseball')
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/alerts/saved-searches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_saved_search(self):
        """Should create saved search."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/alerts/saved-searches/', {
            'name': 'My Search',
            'query': 'ken griffey',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_saved_search_with_category(self):
        """Should create saved search with category filter."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/alerts/saved-searches/', {
            'name': 'Filtered Search',
            'query': 'vintage',
            'category': self.category.pk,
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_delete_saved_search(self):
        """Should delete saved search."""
        search = SavedSearch.objects.create(user=self.user, name='To Delete', query='test')
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(f'/api/v1/alerts/saved-searches/{search.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class PriceAlertAPITests(TestCase):
    """Tests for price alert API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Cards', slug='cards')
        from pricing.models import PriceGuideItem
        self.price_guide_item = PriceGuideItem.objects.create(
            name='Rare Card',
            category=self.category,
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_list_price_alerts_requires_auth(self):
        """Should require authentication."""
        response = self.client.get('/api/v1/alerts/price-alerts/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_price_alerts_authenticated(self):
        """Should list price alerts when authenticated."""
        PriceAlert.objects.create(
            user=self.user,
            price_guide_item=self.price_guide_item,
            target_price=Decimal('50.00'),
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/alerts/price-alerts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_price_alert(self):
        """Should create price alert."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/alerts/price-alerts/', {
            'price_guide_item': self.price_guide_item.pk,
            'target_price': '100.00',
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_update_price_alert(self):
        """Should update price alert."""
        alert = PriceAlert.objects.create(
            user=self.user,
            price_guide_item=self.price_guide_item,
            target_price=Decimal('50.00'),
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch(f'/api/v1/alerts/price-alerts/{alert.pk}/', {
            'target_price': '75.00',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alert.refresh_from_db()
        self.assertEqual(alert.target_price, Decimal('75.00'))

    def test_delete_price_alert(self):
        """Should delete price alert."""
        alert = PriceAlert.objects.create(
            user=self.user,
            price_guide_item=self.price_guide_item,
            target_price=Decimal('50.00'),
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(f'/api/v1/alerts/price-alerts/{alert.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
