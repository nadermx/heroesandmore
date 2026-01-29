from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from items.models import Category, Item


class Listing(models.Model):
    CONDITION_CHOICES = [
        ('mint', 'Mint'),
        ('near_mint', 'Near Mint'),
        ('excellent', 'Excellent'),
        ('very_good', 'Very Good'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    LISTING_TYPE_CHOICES = [
        ('fixed', 'Fixed Price'),
        ('auction', 'Auction'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('sold', 'Sold'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    GRADING_SERVICE_CHOICES = [
        ('', 'None'),
        ('psa', 'PSA'),
        ('bgs', 'BGS'),
        ('cgc', 'CGC'),
        ('sgc', 'SGC'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name='listings')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='listings')

    title = models.CharField(max_length=200)
    description = models.TextField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)

    # Grading info
    grading_service = models.CharField(max_length=10, choices=GRADING_SERVICE_CHOICES, blank=True)
    grade = models.CharField(max_length=20, blank=True)
    cert_number = models.CharField(max_length=50, blank=True, help_text="Certificate number")

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES, default='fixed')
    auction_end = models.DateTimeField(null=True, blank=True)
    reserve_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    allow_offers = models.BooleanField(default=False)

    # Images
    image1 = models.ImageField(upload_to='listings/')
    image2 = models.ImageField(upload_to='listings/', blank=True, null=True)
    image3 = models.ImageField(upload_to='listings/', blank=True, null=True)
    image4 = models.ImageField(upload_to='listings/', blank=True, null=True)
    image5 = models.ImageField(upload_to='listings/', blank=True, null=True)

    # Shipping
    shipping_price = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    ships_from = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    views = models.PositiveIntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['status', '-created']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['seller', 'status']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('marketplace:listing_detail', kwargs={'pk': self.pk})

    def get_images(self):
        """Return list of all images"""
        images = [self.image1]
        for img in [self.image2, self.image3, self.image4, self.image5]:
            if img:
                images.append(img)
        return images

    def get_current_price(self):
        """For auctions, return current highest bid or starting price"""
        if self.listing_type == 'auction':
            highest_bid = self.bids.order_by('-amount').first()
            if highest_bid:
                return highest_bid.amount
        return self.price

    def get_total_price(self):
        """Price including shipping"""
        return self.get_current_price() + self.shipping_price

    def is_auction_ended(self):
        if self.listing_type != 'auction':
            return False
        return self.auction_end and timezone.now() > self.auction_end

    def time_remaining(self):
        if self.listing_type != 'auction' or not self.auction_end:
            return None
        remaining = self.auction_end - timezone.now()
        if remaining.total_seconds() < 0:
            return None
        return remaining


class Bid(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-amount']

    def __str__(self):
        return f"{self.bidder.username} bid ${self.amount} on {self.listing.title}"


class Offer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('countered', 'Countered'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='offers')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='offers_made')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    counter_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Offer ${self.amount} on {self.listing.title}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, related_name='orders')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')

    # Pricing
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_price = models.DecimalField(max_digits=6, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Total
    platform_fee = models.DecimalField(max_digits=8, decimal_places=2)
    seller_payout = models.DecimalField(max_digits=10, decimal_places=2)

    # Payment
    stripe_payment_intent = models.CharField(max_length=100, blank=True)
    stripe_transfer_id = models.CharField(max_length=100, blank=True)

    # Shipping
    shipping_address = models.TextField()
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_carrier = models.CharField(max_length=50, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Order #{self.pk} - {self.listing.title if self.listing else 'Deleted listing'}"

    def get_absolute_url(self):
        return reverse('marketplace:order_detail', kwargs={'pk': self.pk})


class Review(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    text = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"{self.reviewer.username} rated {self.seller.username} {self.rating}/5"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update seller's rating
        self.seller.profile.update_rating()


class SavedListing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_listings')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='saves')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'listing']

    def __str__(self):
        return f"{self.user.username} saved {self.listing.title}"
