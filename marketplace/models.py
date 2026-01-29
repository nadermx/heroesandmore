from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal

from items.models import Category, Item


class AuctionEvent(models.Model):
    """
    Scheduled auction events (weekly auctions, themed events, etc.)
    """
    EVENT_TYPES = [
        ('weekly', 'Weekly Auction'),
        ('themed', 'Themed Event'),
        ('elite', 'Elite Auction'),
        ('flash', 'Flash Sale'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('preview', 'Preview'),
        ('live', 'Live'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField(blank=True)

    # Timing
    preview_start = models.DateTimeField()  # When items visible
    bidding_start = models.DateTimeField()  # When bidding opens
    bidding_end = models.DateTimeField()  # Scheduled end

    # Display
    cover_image = models.ImageField(upload_to='auction_events/', blank=True)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Stats (cached)
    total_lots = models.IntegerField(default=0)
    total_bids = models.IntegerField(default=0)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auction_events_created')

    class Meta:
        ordering = ['-bidding_start']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('marketplace:auction_event_detail', kwargs={'slug': self.slug})

    def is_preview(self):
        now = timezone.now()
        return self.preview_start <= now < self.bidding_start

    def is_live(self):
        now = timezone.now()
        return self.bidding_start <= now < self.bidding_end

    def is_ended(self):
        return timezone.now() >= self.bidding_end

    def time_until_start(self):
        if self.is_live() or self.is_ended():
            return None
        return self.bidding_start - timezone.now()

    def time_remaining(self):
        if not self.is_live():
            return None
        return self.bidding_end - timezone.now()


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
    is_graded = models.BooleanField(default=False)

    # Price guide link
    price_guide_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='listings'
    )

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES, default='fixed')
    auction_end = models.DateTimeField(null=True, blank=True)
    reserve_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    no_reserve = models.BooleanField(default=True)
    starting_bid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.99'))
    allow_offers = models.BooleanField(default=False)
    minimum_offer_percent = models.IntegerField(default=70, help_text="Minimum offer as % of price")

    # Auction event link
    auction_event = models.ForeignKey(
        'AuctionEvent',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='listings'
    )
    lot_number = models.IntegerField(null=True, blank=True)

    # Extended bidding (anti-sniping)
    use_extended_bidding = models.BooleanField(default=True)
    extended_bidding_minutes = models.IntegerField(default=15)
    times_extended = models.IntegerField(default=0)

    # Image recognition
    auto_identified = models.BooleanField(default=False)
    identification_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

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

    # Auto-bid (proxy bidding) support
    is_auto_bid = models.BooleanField(default=False)
    max_bid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Extended bidding trigger
    triggered_extension = models.BooleanField(default=False)

    # Was this the winning bid
    is_winning = models.BooleanField(default=False)

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
        ('withdrawn', 'Withdrawn'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='offers')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='offers_made')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField(blank=True, max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Counter offer
    counter_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    counter_message = models.TextField(blank=True, max_length=500)
    countered_at = models.DateTimeField(null=True, blank=True)

    # Timing
    expires_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Offer ${self.amount} on {self.listing.title}"

    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def can_respond(self):
        return self.status == 'pending' and not self.is_expired()

    def can_accept_counter(self):
        return self.status == 'countered' and not self.is_expired()


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
