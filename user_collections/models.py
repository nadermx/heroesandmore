from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal

from items.models import Category, Item
from marketplace.models import Listing


class Collection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='item_collections')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    cover_image = models.ImageField(upload_to='collections/', blank=True, null=True)

    # Cached value tracking (updated by Celery task)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    value_updated_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated']
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.user.username}'s {self.name}"

    def get_absolute_url(self):
        return reverse('collections:collection_detail', kwargs={'pk': self.pk})

    def get_total_value(self):
        """Calculate total estimated value of collection"""
        total = Decimal('0.00')
        for item in self.items.all():
            if item.current_value:
                total += item.current_value
        return total

    def get_total_cost(self):
        """Calculate total purchase cost"""
        total = Decimal('0.00')
        for item in self.items.all():
            if item.purchase_price:
                total += item.purchase_price
        return total

    def item_count(self):
        return self.items.count()


class CollectionItem(models.Model):
    CONDITION_CHOICES = [
        ('mint', 'Mint'),
        ('near_mint', 'Near Mint'),
        ('excellent', 'Excellent'),
        ('very_good', 'Very Good'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')

    # Can link to database item or be manual entry
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name='collection_items')
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)

    # Manual entry fields (used if no item link)
    name = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='collection_items/', blank=True, null=True)

    # Link to price guide for auto valuation
    price_guide_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='collection_items'
    )

    # Item details
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    grading_company = models.CharField(max_length=10, blank=True)
    grade = models.CharField(max_length=20, blank=True, help_text="PSA/BGS/CGC grade")
    cert_number = models.CharField(max_length=50, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    # Value tracking
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_updated_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.get_name()

    def get_name(self):
        if self.item:
            return self.item.name
        return self.name or "Unnamed item"

    def get_image(self):
        if self.image:
            return self.image
        if self.item and self.item.images:
            return self.item.images[0] if self.item.images else None
        return None

    def get_gain_loss(self):
        if self.purchase_price and self.current_value:
            return self.current_value - self.purchase_price
        return None

    def get_gain_loss_percent(self):
        gain = self.get_gain_loss()
        if gain and self.purchase_price:
            return (gain / self.purchase_price) * 100
        return None


class CollectionValueSnapshot(models.Model):
    """
    Daily/weekly snapshots of collection value for charts
    """
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='value_snapshots')
    date = models.DateField()
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2)
    item_count = models.IntegerField()

    # Value breakdown by category (optional)
    value_by_category = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['collection', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.collection.name} - {self.date}: ${self.total_value}"

    def get_gain_loss(self):
        return self.total_value - self.total_cost

    def get_gain_loss_percent(self):
        if self.total_cost and self.total_cost > 0:
            return ((self.total_value - self.total_cost) / self.total_cost) * 100
        return Decimal('0')
