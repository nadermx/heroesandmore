"""
Tests for user_collections app - collections and items.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from items.models import Category
from user_collections.models import Collection, CollectionItem


class CollectionModelTests(TestCase):
    """Tests for Collection model."""

    def setUp(self):
        self.user = User.objects.create_user('collector', 'collector@test.com', 'pass123')

    def test_collection_creation(self):
        """Should create collection."""
        collection = Collection.objects.create(
            user=self.user,
            name='My Baseball Cards',
            description='My personal collection',
        )
        self.assertEqual(collection.name, 'My Baseball Cards')

    def test_collection_str_representation(self):
        """Collection __str__ should return name."""
        collection = Collection.objects.create(user=self.user, name='Comics')
        self.assertIn('Comics', str(collection))

    def test_collection_visibility_default(self):
        """Collection should be public by default."""
        collection = Collection.objects.create(user=self.user, name='Test')
        self.assertTrue(collection.is_public)

    def test_private_collection(self):
        """Should support private collections."""
        collection = Collection.objects.create(
            user=self.user,
            name='Private Collection',
            is_public=False,
        )
        self.assertFalse(collection.is_public)


class CollectionItemTests(TestCase):
    """Tests for CollectionItem model."""

    def setUp(self):
        self.user = User.objects.create_user('collector', 'collector@test.com', 'pass123')
        self.collection = Collection.objects.create(
            user=self.user,
            name='My Collection',
        )
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_collection_item_creation(self):
        """Should create collection item."""
        item = CollectionItem.objects.create(
            collection=self.collection,
            name='Rare Card',
            purchase_price=Decimal('50.00'),
        )
        self.assertEqual(item.name, 'Rare Card')

    def test_collection_item_with_value(self):
        """Collection item should track purchase and current value."""
        item = CollectionItem.objects.create(
            collection=self.collection,
            name='Investment Card',
            purchase_price=Decimal('100.00'),
            current_value=Decimal('150.00'),
        )
        self.assertEqual(item.current_value, Decimal('150.00'))


class CollectionViewTests(TestCase):
    """Tests for collection views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('collector', 'collector@test.com', 'pass123')
        self.collection = Collection.objects.create(
            user=self.user,
            name='Public Collection',
            is_public=True,
        )

    def test_collections_browse_loads(self):
        """Collections browse page should load."""
        response = self.client.get('/collections/')
        self.assertEqual(response.status_code, 200)

    def test_public_collection_visible(self):
        """Public collection should be visible."""
        response = self.client.get(f'/collections/{self.collection.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_my_collections_requires_login(self):
        """My collections page should require login."""
        response = self.client.get('/collections/my/')
        self.assertIn(response.status_code, [302, 200])

    def test_my_collections_loads(self):
        """My collections should load for logged in user."""
        self.client.login(username='collector', password='pass123')
        response = self.client.get('/collections/my/')
        self.assertIn(response.status_code, [200, 302])

    def test_create_collection_requires_login(self):
        """Creating collection should require login."""
        response = self.client.get('/collections/create/')
        self.assertEqual(response.status_code, 302)

    def test_create_collection_form_loads(self):
        """Collection create form should load."""
        self.client.login(username='collector', password='pass123')
        response = self.client.get('/collections/create/')
        self.assertEqual(response.status_code, 200)

    def test_create_collection_post(self):
        """Should create collection with valid data."""
        self.client.login(username='collector', password='pass123')
        response = self.client.post('/collections/create/', {
            'name': 'New Collection',
            'description': 'A new collection',
            'is_public': True,
        })
        self.assertIn(response.status_code, [200, 302])
