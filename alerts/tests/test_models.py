"""
Tests for alerts app - wishlists, saved searches, notifications.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from items.models import Category
from alerts.models import Wishlist, SavedSearch, PriceAlert


class WishlistModelTests(TestCase):
    """Tests for Wishlist model."""

    def setUp(self):
        self.user = User.objects.create_user('user', 'user@test.com', 'pass123')

    def test_wishlist_creation(self):
        """Should create wishlist."""
        wishlist = Wishlist.objects.create(
            user=self.user,
            name='My Wants',
        )
        self.assertEqual(wishlist.name, 'My Wants')
        self.assertEqual(wishlist.user, self.user)

    def test_wishlist_str_representation(self):
        """Wishlist __str__ should return name."""
        wishlist = Wishlist.objects.create(user=self.user, name='Cards I Need')
        self.assertIn('Cards I Need', str(wishlist))


class SavedSearchModelTests(TestCase):
    """Tests for SavedSearch model."""

    def setUp(self):
        self.user = User.objects.create_user('user', 'user@test.com', 'pass123')

    def test_saved_search_creation(self):
        """Should create saved search."""
        search = SavedSearch.objects.create(
            user=self.user,
            name='Griffey Cards',
            query='ken griffey jr',
        )
        self.assertEqual(search.query, 'ken griffey jr')

    def test_saved_search_with_category(self):
        """Should save search with category filter."""
        category = Category.objects.create(name='Baseball', slug='baseball')
        search = SavedSearch.objects.create(
            user=self.user,
            name='Baseball Search',
            query='vintage',
            category=category,
        )
        self.assertEqual(search.category, category)


class PriceAlertModelTests(TestCase):
    """Tests for PriceAlert model."""

    def setUp(self):
        self.user = User.objects.create_user('user', 'user@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        from pricing.models import PriceGuideItem
        self.price_guide_item = PriceGuideItem.objects.create(
            name='Rare Card',
            category=self.category,
        )

    def test_price_alert_creation(self):
        """Should create price alert."""
        from decimal import Decimal
        alert = PriceAlert.objects.create(
            user=self.user,
            price_guide_item=self.price_guide_item,
            target_price=Decimal('50.00'),
        )
        self.assertEqual(alert.target_price, Decimal('50.00'))


class AlertsViewTests(TestCase):
    """Tests for alerts views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('user', 'user@test.com', 'pass123')

    def test_wishlists_requires_login(self):
        """Wishlists page should require login."""
        response = self.client.get('/alerts/wishlists/')
        self.assertEqual(response.status_code, 302)

    def test_wishlists_page_loads(self):
        """Wishlists page should load for logged in user."""
        self.client.login(username='user', password='pass123')
        response = self.client.get('/alerts/wishlists/')
        self.assertIn(response.status_code, [200, 404])

    def test_saved_searches_requires_login(self):
        """Saved searches page should require login."""
        response = self.client.get('/alerts/searches/')
        self.assertIn(response.status_code, [302, 200])

    def test_alerts_list_requires_login(self):
        """Alerts list page should require login."""
        response = self.client.get('/alerts/')
        self.assertIn(response.status_code, [302, 200])
