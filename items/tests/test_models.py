"""
Tests for items app - categories and items.
"""
from django.test import TestCase, Client
from items.models import Category, Item


class CategoryModelTests(TestCase):
    """Tests for Category model."""

    def test_category_creation(self):
        """Should create category."""
        category = Category.objects.create(
            name='Trading Cards',
            slug='trading-cards',
        )
        self.assertEqual(category.name, 'Trading Cards')
        self.assertEqual(category.slug, 'trading-cards')

    def test_category_str_representation(self):
        """Category __str__ should return name."""
        category = Category.objects.create(name='Comics', slug='comics')
        self.assertEqual(str(category), 'Comics')

    def test_nested_categories(self):
        """Should support parent-child relationships."""
        parent = Category.objects.create(name='Sports', slug='sports')
        child = Category.objects.create(
            name='Baseball',
            slug='baseball',
            parent=parent,
        )
        self.assertEqual(child.parent, parent)

    def test_category_get_absolute_url(self):
        """Category should have absolute URL."""
        category = Category.objects.create(name='Cards', slug='cards')
        url = category.get_absolute_url()
        self.assertIn('cards', url)


class ItemModelTests(TestCase):
    """Tests for Item model."""

    def setUp(self):
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_item_creation(self):
        """Should create item."""
        item = Item.objects.create(
            name='1989 Upper Deck Ken Griffey Jr.',
            category=self.category,
        )
        self.assertEqual(item.name, '1989 Upper Deck Ken Griffey Jr.')

    def test_item_str_representation(self):
        """Item __str__ should return name."""
        item = Item.objects.create(name='Test Item', category=self.category)
        self.assertEqual(str(item), 'Test Item')


class CategoryViewTests(TestCase):
    """Tests for category views."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_items_home_loads(self):
        """Items home page should load."""
        response = self.client.get('/items/')
        self.assertEqual(response.status_code, 200)

    def test_category_page_loads(self):
        """Category page should load."""
        response = self.client.get(f'/items/{self.category.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_category_shows_name(self):
        """Category page should show category name."""
        response = self.client.get(f'/items/{self.category.slug}/')
        self.assertContains(response, 'Cards')
