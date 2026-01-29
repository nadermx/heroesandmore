from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

from items.models import Category
from marketplace.models import Listing


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.user.username}'s {self.name}"

    def get_absolute_url(self):
        return reverse('alerts:wishlist_detail', kwargs={'pk': self.pk})


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')

    # Search criteria
    search_query = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_condition = models.CharField(max_length=20, blank=True, help_text="Minimum acceptable condition")

    notes = models.TextField(blank=True)
    notify_email = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.search_query or f"Items in {self.category}"

    def get_matching_listings(self):
        """Find listings matching this wishlist item criteria"""
        listings = Listing.objects.filter(status='active')

        if self.search_query:
            listings = listings.filter(
                models.Q(title__icontains=self.search_query) |
                models.Q(description__icontains=self.search_query)
            )

        if self.category:
            listings = listings.filter(category=self.category)

        if self.max_price:
            listings = listings.filter(price__lte=self.max_price)

        return listings.order_by('-created')


class Alert(models.Model):
    ALERT_TYPES = [
        ('price_drop', 'Price Drop'),
        ('new_listing', 'New Listing Match'),
        ('auction_ending', 'Auction Ending Soon'),
        ('outbid', 'Outbid'),
        ('order_update', 'Order Update'),
        ('message', 'New Message'),
        ('review', 'New Review'),
        ('follower', 'New Follower'),
        ('wishlist_match', 'Wishlist Match'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=200, blank=True)
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)

    read = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"{self.alert_type}: {self.title}"


class SavedSearch(models.Model):
    """Saved search for alerts"""
    FREQUENCY_CHOICES = [
        ('instant', 'Instant'),
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=100)

    # Search parameters
    query = models.CharField(max_length=500, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    condition = models.CharField(max_length=20, blank=True)
    listing_type = models.CharField(max_length=10, blank=True)

    # Grading filters
    grading_company = models.CharField(max_length=10, blank=True)
    min_grade = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    # Additional filters stored as JSON
    filters = models.JSONField(default=dict, blank=True)

    # Notifications
    notify_email = models.BooleanField(default=True)
    notify_push = models.BooleanField(default=True)
    notify_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='instant')

    last_notified = models.DateTimeField(null=True, blank=True)
    last_checked = models.DateTimeField(auto_now_add=True)
    matches_count = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Saved searches'

    def __str__(self):
        return self.name

    def get_search_url(self):
        """Build search URL from parameters"""
        params = []
        if self.query:
            params.append(f'q={self.query}')
        if self.category:
            params.append(f'category={self.category.slug}')
        if self.min_price:
            params.append(f'min_price={self.min_price}')
        if self.max_price:
            params.append(f'max_price={self.max_price}')
        if self.condition:
            params.append(f'condition={self.condition}')
        if self.listing_type:
            params.append(f'type={self.listing_type}')
        if self.grading_company:
            params.append(f'grading={self.grading_company}')

        return '/items/search/?' + '&'.join(params) if params else '/items/search/'

    def get_matching_listings(self):
        """Find listings matching this saved search criteria"""
        from marketplace.models import Listing
        listings = Listing.objects.filter(status='active')

        if self.query:
            listings = listings.filter(
                models.Q(title__icontains=self.query) |
                models.Q(description__icontains=self.query)
            )
        if self.category:
            listings = listings.filter(category=self.category)
        if self.min_price:
            listings = listings.filter(price__gte=self.min_price)
        if self.max_price:
            listings = listings.filter(price__lte=self.max_price)
        if self.condition:
            listings = listings.filter(condition=self.condition)
        if self.listing_type:
            listings = listings.filter(listing_type=self.listing_type)
        if self.grading_company:
            listings = listings.filter(grading_service=self.grading_company)

        return listings.order_by('-created')


class PriceAlert(models.Model):
    """
    Alert when item drops below target price
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    price_guide_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        on_delete=models.CASCADE,
        related_name='price_alerts'
    )
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    grade = models.CharField(max_length=20, blank=True)  # Any grade or specific

    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    triggered_listing = models.ForeignKey(
        Listing,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='triggered_alerts'
    )

    notify_email = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Alert: {self.price_guide_item.name} under ${self.target_price}"
