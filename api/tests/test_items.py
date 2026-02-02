"""
Tests for items API - categories, items, search.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from items.models import Category, Item


class CategoryAPITests(TestCase):
    """Tests for category API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.parent_category = Category.objects.create(
            name='Sports',
            slug='sports',
        )
        self.child_category = Category.objects.create(
            name='Baseball',
            slug='baseball',
            parent=self.parent_category,
        )

    def test_list_categories(self):
        """Should list top-level categories."""
        response = self.client.get('/api/v1/items/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_category_detail(self):
        """Should get category with children."""
        response = self.client.get(f'/api/v1/items/categories/{self.parent_category.slug}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Sports')

    def test_category_tree(self):
        """Should show category hierarchy."""
        response = self.client.get('/api/v1/items/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ItemSearchAPITests(TestCase):
    """Tests for item search API."""

    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_global_search(self):
        """Should search across items."""
        response = self.client.get('/api/v1/items/search/?q=griffey')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_autocomplete(self):
        """Should provide search autocomplete."""
        response = self.client.get('/api/v1/items/autocomplete/?q=grif')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_with_category_filter(self):
        """Should search within category."""
        response = self.client.get(f'/api/v1/items/search/?q=vintage&category={self.category.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
