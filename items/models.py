from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap icon class")
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def get_absolute_url(self):
        return reverse('items:category', kwargs={'slug': self.slug})

    def get_ancestors(self):
        """Get all parent categories"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """Get all child categories recursively"""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class Item(models.Model):
    """Base item in the database (collectible template)"""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    description = models.TextField(blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    images = models.JSONField(default=list, blank=True)

    # Attributes stored as JSON for flexibility
    # e.g., {"card_number": "123", "set": "Base Set", "player": "Michael Jordan"}
    attributes = models.JSONField(default=dict, blank=True)

    # Price tracking
    estimated_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_updated = models.DateTimeField(null=True, blank=True)

    is_verified = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['slug', 'category']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('items:item_detail', kwargs={'category_slug': self.category.slug, 'slug': self.slug})


class PriceHistory(models.Model):
    """Track price changes over time"""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=50, blank=True)  # e.g., 'sale', 'estimate'
    recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded']
        verbose_name_plural = 'Price histories'

    def __str__(self):
        return f"{self.item.name} - ${self.price} on {self.recorded.date()}"
