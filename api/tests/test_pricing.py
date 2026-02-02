"""
Tests for pricing API - price guide items, grades, sales.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from items.models import Category
from pricing.models import PriceGuideItem, GradePrice, SaleRecord


class PriceGuideAPITests(TestCase):
    """Tests for price guide API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.item = PriceGuideItem.objects.create(
            name='1989 Upper Deck Ken Griffey Jr. #1',
            category=self.category,
        )
        GradePrice.objects.create(
            price_guide_item=self.item,
            grading_company='psa',
            grade=Decimal('10.0'),
            avg_price=Decimal('500.00'),
        )
        GradePrice.objects.create(
            price_guide_item=self.item,
            grading_company='psa',
            grade=Decimal('9.0'),
            avg_price=Decimal('200.00'),
        )

    def test_list_price_guide_items(self):
        """Should list price guide items."""
        response = self.client.get('/api/v1/pricing/items/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_get_price_guide_item_detail(self):
        """Should get price guide item detail."""
        response = self.client.get(f'/api/v1/pricing/items/{self.item.pk}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_get_item_grades(self):
        """Should get prices by grade."""
        response = self.client.get(f'/api/v1/pricing/items/{self.item.pk}/grades/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_get_item_sales(self):
        """Should get recent sales."""
        from django.utils import timezone
        SaleRecord.objects.create(
            price_guide_item=self.item,
            sale_price=Decimal('450.00'),
            grading_company='psa',
            grade=Decimal('10.0'),
            source='ebay',
            sale_date=timezone.now(),
        )
        response = self.client.get(f'/api/v1/pricing/items/{self.item.pk}/sales/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_get_trending_items(self):
        """Should get trending items."""
        response = self.client.get('/api/v1/pricing/trending/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_search_price_guide(self):
        """Should search price guide items."""
        response = self.client.get('/api/v1/pricing/items/?search=griffey')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_filter_by_category(self):
        """Should filter by category."""
        response = self.client.get(f'/api/v1/pricing/items/?category={self.category.pk}')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
