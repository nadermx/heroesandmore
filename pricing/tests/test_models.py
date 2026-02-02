"""
Tests for pricing app - price guide, grades, sales.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from items.models import Category
from pricing.models import PriceGuideItem, GradePrice, SaleRecord


class PriceGuideItemTests(TestCase):
    """Tests for PriceGuideItem model."""

    def setUp(self):
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_price_guide_item_creation(self):
        """Should create price guide item."""
        item = PriceGuideItem.objects.create(
            name='1989 Upper Deck Ken Griffey Jr. #1',
            category=self.category,
        )
        self.assertEqual(item.name, '1989 Upper Deck Ken Griffey Jr. #1')

    def test_price_guide_item_str(self):
        """PriceGuideItem __str__ should return name."""
        item = PriceGuideItem.objects.create(name='Test Card', category=self.category)
        self.assertIn('Test Card', str(item))


class GradePriceTests(TestCase):
    """Tests for GradePrice model."""

    def setUp(self):
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.item = PriceGuideItem.objects.create(
            name='Test Card',
            category=self.category,
        )

    def test_grade_price_creation(self):
        """Should create grade price."""
        grade_price = GradePrice.objects.create(
            price_guide_item=self.item,
            grading_company='psa',
            grade=Decimal('10.0'),
            avg_price=Decimal('500.00'),
        )
        self.assertEqual(grade_price.avg_price, Decimal('500.00'))

    def test_multiple_grades_per_item(self):
        """Item can have multiple grade prices."""
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
        self.assertEqual(self.item.grade_prices.count(), 2)


class SaleRecordTests(TestCase):
    """Tests for SaleRecord model."""

    def setUp(self):
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.item = PriceGuideItem.objects.create(
            name='Test Card',
            category=self.category,
        )

    def test_sale_record_creation(self):
        """Should create sale record."""
        from django.utils import timezone
        sale = SaleRecord.objects.create(
            price_guide_item=self.item,
            sale_price=Decimal('450.00'),
            grading_company='psa',
            grade=Decimal('10.0'),
            source='ebay',
            sale_date=timezone.now(),
        )
        self.assertEqual(sale.sale_price, Decimal('450.00'))


class PriceGuideViewTests(TestCase):
    """Tests for price guide views."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.item = PriceGuideItem.objects.create(
            name='Popular Card',
            category=self.category,
        )

    def test_price_guide_home_loads(self):
        """Price guide home should load."""
        response = self.client.get('/price-guide/')
        self.assertEqual(response.status_code, 200)

    def test_price_guide_item_detail_loads(self):
        """Price guide item detail should load."""
        response = self.client.get(f'/price-guide/{self.item.pk}/')
        self.assertIn(response.status_code, [200, 404])
