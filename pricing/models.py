from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify


class PriceGuideItem(models.Model):
    """
    Master catalog of items with pricing data.
    One entry per unique item (e.g., "1986 Fleer Michael Jordan #57")
    """
    name = models.CharField(max_length=500, db_index=True)
    slug = models.SlugField(max_length=550, unique=True)
    category = models.ForeignKey('items.Category', on_delete=models.CASCADE, related_name='price_guide_items')

    # Item identifiers
    year = models.IntegerField(null=True, blank=True, db_index=True)
    set_name = models.CharField(max_length=200, blank=True)  # "Fleer", "Topps Chrome"
    card_number = models.CharField(max_length=50, blank=True)  # "#57", "RC-1"
    variant = models.CharField(max_length=200, blank=True)  # "Refractor", "1st Print"

    # For comics
    publisher = models.CharField(max_length=100, blank=True)
    volume = models.IntegerField(null=True, blank=True)
    issue_number = models.CharField(max_length=20, blank=True)

    # Metadata
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='price_guide/', blank=True)
    image_source_url = models.URLField(max_length=500, blank=True)
    image_source = models.CharField(max_length=20, blank=True)  # ebay, heritage, gocollect

    # Cached stats (updated by Celery)
    total_sales = models.IntegerField(default=0)
    avg_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    last_sale_date = models.DateTimeField(null=True, blank=True)
    price_trend = models.CharField(max_length=10, default='stable')  # up, down, stable

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_sales', 'name']
        indexes = [
            models.Index(fields=['name', 'year']),
            models.Index(fields=['category', 'year']),
            models.Index(fields=['set_name', 'year']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.year or ''}-{self.name}")[:500]
            self.slug = base_slug
            counter = 1
            while PriceGuideItem.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('pricing:price_guide_detail', kwargs={'slug': self.slug})

    def get_price_for_grade(self, grading_company='raw', grade=None):
        """Get price data for a specific grade"""
        try:
            if grade:
                return self.grade_prices.get(grading_company=grading_company, grade=grade)
            return self.grade_prices.filter(grading_company=grading_company).first()
        except GradePrice.DoesNotExist:
            return None


class GradePrice(models.Model):
    """
    Price data for each grade of an item.
    """
    GRADING_COMPANIES = [
        ('raw', 'Raw/Ungraded'),
        ('psa', 'PSA'),
        ('bgs', 'BGS'),
        ('cgc', 'CGC'),
        ('sgc', 'SGC'),
        ('cbcs', 'CBCS'),
    ]

    price_guide_item = models.ForeignKey(PriceGuideItem, on_delete=models.CASCADE, related_name='grade_prices')
    grading_company = models.CharField(max_length=10, choices=GRADING_COMPANIES)
    grade = models.DecimalField(max_digits=3, decimal_places=1)  # 10.0, 9.5, 9.0, etc.

    # Price data
    avg_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    low_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    high_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    median_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Stats
    num_sales = models.IntegerField(default=0)
    last_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    last_sale_date = models.DateTimeField(null=True, blank=True)

    # 30-day change
    price_change_30d = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # percentage

    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['price_guide_item', 'grading_company', 'grade']
        ordering = ['-grade']

    def __str__(self):
        return f"{self.price_guide_item.name} - {self.get_grading_company_display()} {self.grade}"


class SaleRecord(models.Model):
    """
    Individual sale records for price tracking.
    """
    SOURCES = [
        ('heroesandmore', 'HeroesAndMore'),
        ('ebay', 'eBay'),
        ('heritage', 'Heritage Auctions'),
        ('gocollect', 'GoCollect'),
        ('goldin', 'Goldin'),
        ('pwcc', 'PWCC'),
        ('manual', 'Manual Entry'),
    ]

    price_guide_item = models.ForeignKey(PriceGuideItem, on_delete=models.CASCADE, related_name='sales')

    sale_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_date = models.DateTimeField()
    source = models.CharField(max_length=20, choices=SOURCES)
    source_url = models.URLField(blank=True)

    grading_company = models.CharField(max_length=10, blank=True)
    grade = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    cert_number = models.CharField(max_length=50, blank=True)

    # Link to our listing if sold here
    listing = models.ForeignKey('marketplace.Listing', null=True, blank=True, on_delete=models.SET_NULL)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['price_guide_item', 'sale_date']),
            models.Index(fields=['sale_date']),
        ]

    def __str__(self):
        return f"{self.price_guide_item.name} sold for ${self.sale_price} on {self.sale_date.date()}"
