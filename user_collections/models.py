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

    # Item details
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    grade = models.CharField(max_length=20, blank=True, help_text="PSA/BGS/CGC grade")
    quantity = models.PositiveIntegerField(default=1)

    # Value tracking
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

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
