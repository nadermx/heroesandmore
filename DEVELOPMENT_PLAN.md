# HeroesAndMore Development Plan - Complete Implementation Guide

## Overview

This document provides the complete technical specification for implementing all missing features identified in the competitor analysis. This covers everything except the mobile app.

**Estimated Total: 12 weeks of development**

---

## Table of Contents

1. [Database Schema Changes](#1-database-schema-changes)
2. [Phase 1: Price Guide System](#2-phase-1-price-guide-system)
3. [Phase 2: Image Recognition Scanner](#3-phase-2-image-recognition-scanner)
4. [Phase 3: Collection Portfolio & Value Tracking](#4-phase-3-collection-portfolio--value-tracking)
5. [Phase 4: Live Bidding System](#5-phase-4-live-bidding-system)
6. [Phase 5: Auction Events](#6-phase-5-auction-events)
7. [Phase 6: Offer/Counteroffer System](#7-phase-6-offercounteroffer-system)
8. [Phase 7: Seller Tools](#8-phase-7-seller-tools)
9. [Phase 8: Enhanced Search & Notifications](#9-phase-8-enhanced-search--notifications)
10. [Phase 9: Trust & Safety](#10-phase-9-trust--safety)
11. [Infrastructure Requirements](#11-infrastructure-requirements)
12. [File Structure](#12-file-structure)

---

## 1. Database Schema Changes

### New App: `pricing`
Handles price guide, valuation, and market data.

```python
# pricing/models.py

class PriceGuideItem(models.Model):
    """
    Master catalog of items with pricing data.
    One entry per unique item (e.g., "1986 Fleer Michael Jordan #57")
    """
    name = models.CharField(max_length=500, db_index=True)
    slug = models.SlugField(max_length=550, unique=True)
    category = models.ForeignKey('items.Category', on_delete=models.CASCADE)

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

    # Cached stats (updated by Celery)
    total_sales = models.IntegerField(default=0)
    avg_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    last_sale_date = models.DateTimeField(null=True)
    price_trend = models.CharField(max_length=10, default='stable')  # up, down, stable

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'year']),
            models.Index(fields=['category', 'year']),
        ]


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
    avg_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    low_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    high_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    median_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)

    # Stats
    num_sales = models.IntegerField(default=0)
    last_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    last_sale_date = models.DateTimeField(null=True)

    # 30-day change
    price_change_30d = models.DecimalField(max_digits=5, decimal_places=2, null=True)  # percentage

    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['price_guide_item', 'grading_company', 'grade']


class SaleRecord(models.Model):
    """
    Individual sale records for price tracking.
    """
    SOURCES = [
        ('heroesandmore', 'HeroesAndMore'),
        ('ebay', 'eBay'),
        ('heritage', 'Heritage Auctions'),
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
    grade = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    cert_number = models.CharField(max_length=50, blank=True)

    # Link to our listing if sold here
    listing = models.ForeignKey('marketplace.Listing', null=True, blank=True, on_delete=models.SET_NULL)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['price_guide_item', 'sale_date']),
            models.Index(fields=['sale_date']),
        ]
```

### Updates to `marketplace/models.py`

```python
# Add to Listing model

class Listing(models.Model):
    # ... existing fields ...

    # Price guide link
    price_guide_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='listings'
    )

    # Grading info (enhanced)
    grading_company = models.CharField(max_length=10, choices=GRADING_COMPANIES, blank=True)
    grade = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    cert_number = models.CharField(max_length=50, blank=True)
    is_graded = models.BooleanField(default=False)

    # Auction enhancements
    auction_event = models.ForeignKey(
        'AuctionEvent',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='listings'
    )
    lot_number = models.IntegerField(null=True, blank=True)
    starting_bid = models.DecimalField(max_digits=10, decimal_places=2, default=0.99)
    reserve_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    no_reserve = models.BooleanField(default=True)

    # Extended bidding
    use_extended_bidding = models.BooleanField(default=True)
    extended_bidding_minutes = models.IntegerField(default=15)
    times_extended = models.IntegerField(default=0)

    # Allow offers
    allow_offers = models.BooleanField(default=False)
    minimum_offer_percent = models.IntegerField(default=70)  # Min 70% of price

    # Image recognition
    auto_identified = models.BooleanField(default=False)
    identification_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True)


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
    is_published = models.BooleanField(default=False)

    # Stats (cached)
    total_lots = models.IntegerField(default=0)
    total_bids = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)


class Bid(models.Model):
    # ... existing fields ...

    # Auto-bid support
    is_auto_bid = models.BooleanField(default=False)
    max_bid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Extended bidding trigger
    triggered_extension = models.BooleanField(default=False)


class Offer(models.Model):
    """
    Make Offer / Counteroffer system
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('countered', 'Countered'),
        ('expired', 'Expired'),
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
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
```

### Updates to `collections/models.py`

```python
class Collection(models.Model):
    # ... existing fields ...

    # Value tracking
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    value_updated_at = models.DateTimeField(null=True)


class CollectionItem(models.Model):
    # ... existing fields ...

    # Link to price guide
    price_guide_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    # Grading
    grading_company = models.CharField(max_length=10, blank=True)
    grade = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    cert_number = models.CharField(max_length=50, blank=True)

    # Value tracking
    current_value = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    value_updated_at = models.DateTimeField(null=True)


class CollectionValueSnapshot(models.Model):
    """
    Daily/weekly snapshots of collection value for charts
    """
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='snapshots')
    date = models.DateField()
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2)
    item_count = models.IntegerField()

    class Meta:
        unique_together = ['collection', 'date']
        ordering = ['-date']
```

### New App: `scanner`

```python
# scanner/models.py

class ScanResult(models.Model):
    """
    Store image recognition results
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='scans/')

    # Recognition results
    identified_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    # Extracted data
    extracted_data = models.JSONField(default=dict)
    # {
    #   'title': 'Michael Jordan',
    #   'year': 1986,
    #   'set': 'Fleer',
    #   'card_number': '57',
    #   'grading_company': 'PSA',
    #   'grade': '10',
    #   'cert_number': '12345678'
    # }

    # Status
    status = models.CharField(max_length=20, default='pending')  # pending, success, failed
    error_message = models.TextField(blank=True)

    # What user did with it
    converted_to_listing = models.ForeignKey(
        'marketplace.Listing',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    added_to_collection = models.ForeignKey(
        'collections.CollectionItem',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    created = models.DateTimeField(auto_now_add=True)
```

### Updates to `alerts/models.py`

```python
class SavedSearch(models.Model):
    """
    Saved searches with notification preferences
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=100)

    # Search parameters
    query = models.CharField(max_length=500, blank=True)
    category = models.ForeignKey('items.Category', null=True, blank=True, on_delete=models.SET_NULL)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    condition = models.CharField(max_length=20, blank=True)
    grading_company = models.CharField(max_length=10, blank=True)
    min_grade = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    listing_type = models.CharField(max_length=20, blank=True)  # auction, fixed, all

    # Stored as JSON for flexibility
    filters = models.JSONField(default=dict)

    # Notifications
    notify_email = models.BooleanField(default=True)
    notify_push = models.BooleanField(default=True)
    notify_frequency = models.CharField(max_length=20, default='instant')
    # instant, daily_digest, weekly_digest

    last_notified = models.DateTimeField(null=True)
    matches_count = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)


class PriceAlert(models.Model):
    """
    Alert when item drops below target price
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    price_guide_item = models.ForeignKey('pricing.PriceGuideItem', on_delete=models.CASCADE)
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    grade = models.CharField(max_length=20, blank=True)  # Any grade or specific

    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True)
    triggered_listing = models.ForeignKey('marketplace.Listing', null=True, on_delete=models.SET_NULL)

    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
```

### Updates to `accounts/models.py`

```python
class Profile(models.Model):
    # ... existing fields ...

    # Seller subscription
    seller_tier = models.CharField(max_length=20, default='starter')
    # starter, basic, featured, premium
    subscription_expires = models.DateTimeField(null=True, blank=True)

    # Seller verification
    is_verified_seller = models.BooleanField(default=False)
    id_verified = models.BooleanField(default=False)
    address_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True)

    # Stats
    total_sales_count = models.IntegerField(default=0)
    total_sales_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Recently viewed (for recommendations)
    recently_viewed = models.ManyToManyField('marketplace.Listing', blank=True, related_name='viewed_by')


class RecentlyViewed(models.Model):
    """
    Track recently viewed items with timestamp
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    listing = models.ForeignKey('marketplace.Listing', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)
    view_count = models.IntegerField(default=1)

    class Meta:
        unique_together = ['user', 'listing']
        ordering = ['-viewed_at']
```

### New: `seller_tools/models.py`

```python
# seller_tools/models.py

class BulkImport(models.Model):
    """
    Track bulk listing imports
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='bulk_imports/')
    file_type = models.CharField(max_length=20)  # csv, xlsx

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)

    errors = models.JSONField(default=list)  # [{row: 5, error: "Invalid price"}]

    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)


class BulkImportRow(models.Model):
    """
    Individual rows from bulk import
    """
    bulk_import = models.ForeignKey(BulkImport, on_delete=models.CASCADE, related_name='rows')
    row_number = models.IntegerField()
    data = models.JSONField()

    status = models.CharField(max_length=20, default='pending')
    error_message = models.TextField(blank=True)

    listing = models.ForeignKey(
        'marketplace.Listing',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )


class SellerSubscription(models.Model):
    """
    Seller subscription management
    """
    TIERS = [
        ('starter', 'Starter'),
        ('basic', 'Basic'),
        ('featured', 'Featured'),
        ('premium', 'Premium'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tier = models.CharField(max_length=20, choices=TIERS, default='starter')

    # Limits
    max_active_listings = models.IntegerField(default=50)
    commission_rate = models.DecimalField(max_digits=4, decimal_places=2, default=12.95)
    featured_slots = models.IntegerField(default=0)

    # Billing
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    current_period_start = models.DateTimeField(null=True)
    current_period_end = models.DateTimeField(null=True)

    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
```

---

## 2. Phase 1: Price Guide System

### Files to Create

```
pricing/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── urls.py
├── views.py
├── serializers.py
├── services/
│   ├── __init__.py
│   ├── price_calculator.py
│   └── data_import.py
├── tasks.py  # Celery tasks
└── templates/
    └── pricing/
        ├── price_guide_list.html
        ├── price_guide_detail.html
        ├── price_chart.html
        └── components/
            ├── price_card.html
            └── price_history_chart.html
```

### Key Views

```python
# pricing/views.py

class PriceGuideListView(ListView):
    """Browse price guide by category"""
    model = PriceGuideItem
    template_name = 'pricing/price_guide_list.html'
    paginate_by = 48

    def get_queryset(self):
        qs = super().get_queryset()

        # Category filter
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        # Search
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)

        # Year filter
        year = self.request.GET.get('year')
        if year:
            qs = qs.filter(year=year)

        # Sort
        sort = self.request.GET.get('sort', 'popular')
        if sort == 'popular':
            qs = qs.order_by('-total_sales')
        elif sort == 'newest':
            qs = qs.order_by('-created')
        elif sort == 'price_high':
            qs = qs.order_by('-avg_sale_price')
        elif sort == 'price_low':
            qs = qs.order_by('avg_sale_price')

        return qs


class PriceGuideDetailView(DetailView):
    """Individual item price guide with charts"""
    model = PriceGuideItem
    template_name = 'pricing/price_guide_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object

        # Grade prices
        context['grade_prices'] = item.grade_prices.all().order_by('-grade')

        # Recent sales
        context['recent_sales'] = item.sales.order_by('-sale_date')[:20]

        # Price history for charts (last 12 months)
        context['price_history'] = self.get_price_history(item)

        # Active listings for this item
        context['active_listings'] = Listing.objects.filter(
            price_guide_item=item,
            status='active'
        ).order_by('price')[:10]

        return context

    def get_price_history(self, item):
        """Get price history grouped by month for charts"""
        from django.db.models.functions import TruncMonth
        from django.db.models import Avg

        twelve_months_ago = timezone.now() - timedelta(days=365)

        return item.sales.filter(
            sale_date__gte=twelve_months_ago
        ).annotate(
            month=TruncMonth('sale_date')
        ).values('month').annotate(
            avg_price=Avg('sale_price')
        ).order_by('month')


def get_price_suggestion(request):
    """AJAX endpoint for price suggestions when listing"""
    item_name = request.GET.get('name', '')
    category_id = request.GET.get('category')
    grade = request.GET.get('grade')
    grading_company = request.GET.get('grading_company', 'raw')

    # Find matching price guide item
    item = PriceGuideItem.objects.filter(
        name__icontains=item_name,
        category_id=category_id
    ).first()

    if not item:
        return JsonResponse({'found': False})

    # Get price for grade
    grade_price = item.grade_prices.filter(
        grading_company=grading_company,
        grade=grade
    ).first()

    if grade_price:
        return JsonResponse({
            'found': True,
            'item_id': item.id,
            'item_name': item.name,
            'suggested_price': float(grade_price.avg_price or 0),
            'low_price': float(grade_price.low_price or 0),
            'high_price': float(grade_price.high_price or 0),
            'num_sales': grade_price.num_sales,
            'last_sale': grade_price.last_sale_date.isoformat() if grade_price.last_sale_date else None,
        })

    return JsonResponse({
        'found': True,
        'item_id': item.id,
        'item_name': item.name,
        'suggested_price': float(item.avg_sale_price or 0),
        'no_grade_data': True,
    })
```

### Celery Tasks

```python
# pricing/tasks.py

from celery import shared_task

@shared_task
def update_price_guide_stats(item_id):
    """Update cached stats for a price guide item"""
    item = PriceGuideItem.objects.get(id=item_id)

    # Update overall stats
    sales = item.sales.all()
    item.total_sales = sales.count()

    if sales.exists():
        item.avg_sale_price = sales.aggregate(Avg('sale_price'))['sale_price__avg']
        item.last_sale_date = sales.order_by('-sale_date').first().sale_date

        # Calculate trend (compare last 30 days to previous 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sixty_days_ago = timezone.now() - timedelta(days=60)

        recent_avg = sales.filter(sale_date__gte=thirty_days_ago).aggregate(
            Avg('sale_price'))['sale_price__avg']
        previous_avg = sales.filter(
            sale_date__gte=sixty_days_ago,
            sale_date__lt=thirty_days_ago
        ).aggregate(Avg('sale_price'))['sale_price__avg']

        if recent_avg and previous_avg:
            change = ((recent_avg - previous_avg) / previous_avg) * 100
            if change > 5:
                item.price_trend = 'up'
            elif change < -5:
                item.price_trend = 'down'
            else:
                item.price_trend = 'stable'

    item.save()

    # Update grade-specific prices
    for gp in item.grade_prices.all():
        grade_sales = sales.filter(
            grading_company=gp.grading_company,
            grade=gp.grade
        )

        if grade_sales.exists():
            prices = list(grade_sales.values_list('sale_price', flat=True))
            gp.num_sales = len(prices)
            gp.avg_price = sum(prices) / len(prices)
            gp.low_price = min(prices)
            gp.high_price = max(prices)
            gp.median_price = sorted(prices)[len(prices) // 2]

            last_sale = grade_sales.order_by('-sale_date').first()
            gp.last_sale_price = last_sale.sale_price
            gp.last_sale_date = last_sale.sale_date

            gp.save()


@shared_task
def record_sale_from_order(order_id):
    """When an order completes, record it in price guide"""
    from marketplace.models import Order
    order = Order.objects.get(id=order_id)
    listing = order.listing

    if listing.price_guide_item:
        SaleRecord.objects.create(
            price_guide_item=listing.price_guide_item,
            sale_price=order.item_price,
            sale_date=order.created,
            source='heroesandmore',
            grading_company=listing.grading_company or '',
            grade=listing.grade,
            cert_number=listing.cert_number or '',
            listing=listing,
        )

        # Trigger stats update
        update_price_guide_stats.delay(listing.price_guide_item.id)
```

---

## 3. Phase 2: Image Recognition Scanner

### Service Implementation

```python
# scanner/services/recognition.py

import os
from google.cloud import vision
from django.conf import settings

class ImageRecognitionService:
    """
    Service for identifying collectibles from images.
    Uses Google Cloud Vision + custom logic.
    """

    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def analyze_image(self, image_path):
        """
        Analyze an image and extract collectible information.
        Returns dict with identified data.
        """
        with open(image_path, 'rb') as f:
            content = f.read()

        image = vision.Image(content=content)

        # Get text from image (OCR)
        text_response = self.client.text_detection(image=image)
        texts = text_response.text_annotations
        full_text = texts[0].description if texts else ''

        # Get labels
        label_response = self.client.label_detection(image=image)
        labels = [label.description.lower() for label in label_response.label_annotations]

        # Determine item type
        item_type = self._determine_item_type(labels, full_text)

        # Extract based on type
        if item_type == 'graded_card':
            return self._extract_graded_card(full_text, labels)
        elif item_type == 'raw_card':
            return self._extract_raw_card(full_text, labels)
        elif item_type == 'comic':
            return self._extract_comic(full_text, labels)
        elif item_type == 'graded_comic':
            return self._extract_graded_comic(full_text, labels)
        else:
            return self._extract_generic(full_text, labels)

    def _determine_item_type(self, labels, text):
        """Determine what type of collectible this is"""
        text_lower = text.lower()

        # Check for grading company labels
        grading_indicators = ['psa', 'bgs', 'cgc', 'sgc', 'cbcs', 'gem mint', 'authentic']
        has_grading = any(g in text_lower for g in grading_indicators)

        # Check for comics
        comic_indicators = ['comic', 'marvel', 'dc', 'image comics', 'dark horse']
        is_comic = any(c in text_lower or c in labels for c in comic_indicators)

        # Check for trading cards
        card_indicators = ['trading card', 'rookie', 'topps', 'panini', 'upper deck', 'fleer']
        is_card = any(c in text_lower or c in labels for c in card_indicators)

        if is_comic and has_grading:
            return 'graded_comic'
        elif is_comic:
            return 'comic'
        elif is_card and has_grading:
            return 'graded_card'
        elif is_card:
            return 'raw_card'
        else:
            return 'unknown'

    def _extract_graded_card(self, text, labels):
        """Extract info from a graded card slab"""
        import re

        result = {
            'type': 'graded_card',
            'confidence': 0.0,
        }

        # Extract grading company
        text_lower = text.lower()
        if 'psa' in text_lower:
            result['grading_company'] = 'PSA'
        elif 'bgs' in text_lower or 'beckett' in text_lower:
            result['grading_company'] = 'BGS'
        elif 'sgc' in text_lower:
            result['grading_company'] = 'SGC'
        elif 'cgc' in text_lower:
            result['grading_company'] = 'CGC'

        # Extract grade (look for patterns like "10", "GEM MINT 10", "9.5")
        grade_patterns = [
            r'gem\s*mint\s*(\d+)',
            r'mint\s*(\d+)',
            r'\b(\d+\.?\d?)\s*/\s*10\b',
            r'\bgrade[:\s]*(\d+\.?\d?)\b',
            r'\b(10|9\.5|9|8\.5|8|7\.5|7|6\.5|6|5\.5|5|4|3|2|1)\b'
        ]

        for pattern in grade_patterns:
            match = re.search(pattern, text_lower)
            if match:
                result['grade'] = match.group(1)
                break

        # Extract cert number (usually 8+ digits)
        cert_match = re.search(r'\b(\d{8,})\b', text)
        if cert_match:
            result['cert_number'] = cert_match.group(1)

        # Extract year
        year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', text)
        if year_match:
            result['year'] = int(year_match.group(1))

        # Extract player/character name (usually largest text)
        # This is simplified - would need more sophisticated NLP
        lines = text.split('\n')
        for line in lines:
            if len(line) > 5 and not any(c.isdigit() for c in line[:3]):
                result['name'] = line.strip()
                break

        # Calculate confidence
        confidence_factors = [
            'grading_company' in result,
            'grade' in result,
            'cert_number' in result,
            'year' in result,
            'name' in result,
        ]
        result['confidence'] = sum(confidence_factors) / len(confidence_factors) * 100

        return result

    def _extract_comic(self, text, labels):
        """Extract info from a comic book"""
        import re

        result = {
            'type': 'comic',
            'confidence': 0.0,
        }

        text_lower = text.lower()

        # Extract publisher
        publishers = {
            'marvel': 'Marvel',
            'dc': 'DC',
            'image': 'Image',
            'dark horse': 'Dark Horse',
            'idw': 'IDW',
            'valiant': 'Valiant',
        }
        for key, value in publishers.items():
            if key in text_lower:
                result['publisher'] = value
                break

        # Extract issue number
        issue_patterns = [
            r'#\s*(\d+)',
            r'issue\s*#?\s*(\d+)',
            r'no\.?\s*(\d+)',
        ]
        for pattern in issue_patterns:
            match = re.search(pattern, text_lower)
            if match:
                result['issue_number'] = match.group(1)
                break

        # Extract title (usually prominent text)
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 3 and line.isupper():
                result['title'] = line.title()
                break

        # Calculate confidence
        confidence_factors = [
            'publisher' in result,
            'issue_number' in result,
            'title' in result,
        ]
        result['confidence'] = sum(confidence_factors) / len(confidence_factors) * 100

        return result

    # ... similar methods for other types


def match_to_price_guide(extracted_data):
    """
    Try to match extracted data to existing price guide item
    """
    from pricing.models import PriceGuideItem
    from django.db.models import Q

    query = Q()

    if extracted_data.get('name'):
        query &= Q(name__icontains=extracted_data['name'])

    if extracted_data.get('year'):
        query &= Q(year=extracted_data['year'])

    if extracted_data.get('cert_number'):
        # Try exact cert match first
        exact_match = PriceGuideItem.objects.filter(
            sales__cert_number=extracted_data['cert_number']
        ).first()
        if exact_match:
            return exact_match, 100.0

    # Fuzzy match
    candidates = PriceGuideItem.objects.filter(query)[:10]

    if candidates.exists():
        # Return best match (simplified - could use fuzzy matching library)
        return candidates.first(), extracted_data.get('confidence', 50.0)

    return None, 0.0
```

### Scanner Views

```python
# scanner/views.py

from django.views.generic import CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

class ScanItemView(LoginRequiredMixin, CreateView):
    """Upload image to scan and identify"""
    model = ScanResult
    fields = ['image']
    template_name = 'scanner/scan_item.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)

        # Process image asynchronously
        from .tasks import process_scan
        process_scan.delay(self.object.id)

        return response

    def get_success_url(self):
        return reverse('scanner:scan_result', kwargs={'pk': self.object.pk})


class ScanResultView(LoginRequiredMixin, DetailView):
    """View scan results and create listing or add to collection"""
    model = ScanResult
    template_name = 'scanner/scan_result.html'

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.object.identified_item:
            # Get price suggestion
            context['price_data'] = self.object.identified_item.grade_prices.filter(
                grading_company=self.object.extracted_data.get('grading_company', 'raw'),
                grade=self.object.extracted_data.get('grade', 0)
            ).first()

        return context


@login_required
def create_listing_from_scan(request, scan_id):
    """Convert scan result to listing"""
    scan = get_object_or_404(ScanResult, id=scan_id, user=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.price_guide_item = scan.identified_item
            listing.auto_identified = True
            listing.identification_confidence = scan.confidence

            # Copy image from scan
            listing.image1 = scan.image

            listing.save()

            scan.converted_to_listing = listing
            scan.save()

            return redirect(listing.get_absolute_url())
    else:
        # Pre-fill form with extracted data
        initial = {
            'title': scan.extracted_data.get('name', ''),
            'grading_company': scan.extracted_data.get('grading_company', ''),
            'grade': scan.extracted_data.get('grade'),
            'cert_number': scan.extracted_data.get('cert_number', ''),
        }

        # Get suggested price
        if scan.identified_item:
            price_point = scan.identified_item.grade_prices.filter(
                grading_company=initial.get('grading_company', 'raw'),
            ).first()
            if price_point:
                initial['price'] = price_point.avg_price

        form = ListingForm(initial=initial)

    return render(request, 'scanner/create_listing.html', {
        'form': form,
        'scan': scan,
    })
```

---

## 4. Phase 3: Collection Portfolio & Value Tracking

### Portfolio Views

```python
# collections/views.py

class PortfolioDashboardView(LoginRequiredMixin, TemplateView):
    """User's collection portfolio with value tracking"""
    template_name = 'collections/portfolio.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get all user's collections
        collections = Collection.objects.filter(user=user)

        # Calculate totals
        total_value = sum(c.total_value for c in collections)
        total_cost = sum(c.total_cost for c in collections)
        total_items = sum(c.items.count() for c in collections)

        context['collections'] = collections
        context['total_value'] = total_value
        context['total_cost'] = total_cost
        context['total_items'] = total_items
        context['total_gain_loss'] = total_value - total_cost
        context['gain_loss_percent'] = (
            ((total_value - total_cost) / total_cost * 100)
            if total_cost > 0 else 0
        )

        # Value history for charts (last 12 months)
        context['value_history'] = self.get_value_history(user)

        # Top gainers/losers
        context['top_gainers'] = self.get_top_movers(user, direction='up')
        context['top_losers'] = self.get_top_movers(user, direction='down')

        return context

    def get_value_history(self, user):
        """Get combined value history across all collections"""
        from django.db.models import Sum
        from django.db.models.functions import TruncDate

        return CollectionValueSnapshot.objects.filter(
            collection__user=user
        ).values('date').annotate(
            total_value=Sum('total_value')
        ).order_by('date')

    def get_top_movers(self, user, direction='up', limit=5):
        """Get items with biggest price changes"""
        items = CollectionItem.objects.filter(
            collection__user=user,
            price_guide_item__isnull=False
        ).select_related('price_guide_item')

        movers = []
        for item in items:
            pg = item.price_guide_item
            if pg.price_trend == direction:
                movers.append({
                    'item': item,
                    'current_value': item.current_value,
                    'purchase_price': item.purchase_price,
                    'change': item.current_value - (item.purchase_price or 0),
                })

        movers.sort(key=lambda x: abs(x['change']), reverse=True)
        return movers[:limit]
```

### Celery Tasks for Value Updates

```python
# collections/tasks.py

@shared_task
def update_collection_values():
    """Daily task to update all collection values"""
    for collection in Collection.objects.all():
        update_single_collection_value.delay(collection.id)


@shared_task
def update_single_collection_value(collection_id):
    """Update value for a single collection"""
    collection = Collection.objects.get(id=collection_id)

    total_value = Decimal('0.00')

    for item in collection.items.all():
        if item.price_guide_item:
            # Get current price for item's grade
            grade_price = item.price_guide_item.grade_prices.filter(
                grading_company=item.grading_company or 'raw',
                grade=item.grade or 0
            ).first()

            if grade_price and grade_price.avg_price:
                item.current_value = grade_price.avg_price
                item.value_updated_at = timezone.now()
                item.save()
                total_value += grade_price.avg_price

    collection.total_value = total_value
    collection.value_updated_at = timezone.now()
    collection.save()

    # Create daily snapshot
    CollectionValueSnapshot.objects.update_or_create(
        collection=collection,
        date=timezone.now().date(),
        defaults={
            'total_value': collection.total_value,
            'total_cost': collection.total_cost,
            'item_count': collection.items.count(),
        }
    )
```

---

## 5. Phase 4: Live Bidding System

### Django Channels Setup

```python
# marketplace/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

class AuctionConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time auction updates"""

    async def connect(self):
        self.listing_id = self.scope['url_route']['kwargs']['listing_id']
        self.room_group_name = f'auction_{self.listing_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send current auction state
        state = await self.get_auction_state()
        await self.send(text_data=json.dumps({
            'type': 'auction_state',
            'data': state
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'place_bid':
            await self.handle_bid(data)
        elif message_type == 'set_max_bid':
            await self.handle_max_bid(data)

    async def handle_bid(self, data):
        """Process a bid"""
        user = self.scope['user']
        if not user.is_authenticated:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You must be logged in to bid'
            }))
            return

        amount = Decimal(str(data['amount']))
        result = await self.place_bid(user, amount)

        if result['success']:
            # Broadcast new bid to all watchers
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'bid_placed',
                    'bid': result['bid_data']
                }
            )
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': result['error']
            }))

    @database_sync_to_async
    def place_bid(self, user, amount):
        """Place bid in database"""
        from .models import Listing, Bid

        listing = Listing.objects.get(id=self.listing_id)

        # Validation
        if listing.status != 'active':
            return {'success': False, 'error': 'Auction has ended'}

        if listing.seller == user:
            return {'success': False, 'error': 'You cannot bid on your own item'}

        current_high = listing.bids.order_by('-amount').first()
        min_bid = (current_high.amount + Decimal('1.00')) if current_high else listing.starting_bid

        if amount < min_bid:
            return {'success': False, 'error': f'Minimum bid is ${min_bid}'}

        # Check for reserve
        if listing.reserve_price and amount < listing.reserve_price:
            reserve_met = False
        else:
            reserve_met = True

        # Create bid
        bid = Bid.objects.create(
            listing=listing,
            bidder=user,
            amount=amount,
        )

        # Extended bidding check
        time_remaining = listing.auction_end - timezone.now()
        if time_remaining.total_seconds() < listing.extended_bidding_minutes * 60:
            listing.auction_end = timezone.now() + timedelta(minutes=listing.extended_bidding_minutes)
            listing.times_extended += 1
            bid.triggered_extension = True
            bid.save()
            listing.save()

        # Handle auto-bids from other users
        self.process_auto_bids(listing, bid)

        # Send notifications
        from alerts.tasks import send_outbid_notification
        if current_high and current_high.bidder != user:
            send_outbid_notification.delay(current_high.bidder.id, listing.id, amount)

        return {
            'success': True,
            'bid_data': {
                'id': bid.id,
                'amount': str(bid.amount),
                'bidder': user.username,
                'time': bid.created.isoformat(),
                'reserve_met': reserve_met,
                'extended': bid.triggered_extension,
                'new_end_time': listing.auction_end.isoformat() if bid.triggered_extension else None,
            }
        }

    def process_auto_bids(self, listing, new_bid):
        """Process any auto-bids that should respond"""
        auto_bids = Bid.objects.filter(
            listing=listing,
            is_auto_bid=True,
            max_bid_amount__gt=new_bid.amount
        ).exclude(bidder=new_bid.bidder).order_by('-max_bid_amount')

        if auto_bids.exists():
            top_auto = auto_bids.first()
            # Place minimum winning bid for auto-bidder
            auto_amount = min(new_bid.amount + Decimal('1.00'), top_auto.max_bid_amount)

            Bid.objects.create(
                listing=listing,
                bidder=top_auto.bidder,
                amount=auto_amount,
                is_auto_bid=True,
                max_bid_amount=top_auto.max_bid_amount,
            )

    @database_sync_to_async
    def get_auction_state(self):
        """Get current auction state"""
        from .models import Listing

        listing = Listing.objects.get(id=self.listing_id)
        bids = listing.bids.order_by('-amount')[:10]

        return {
            'listing_id': listing.id,
            'current_price': str(listing.current_price),
            'bid_count': listing.bids.count(),
            'end_time': listing.auction_end.isoformat(),
            'reserve_met': listing.reserve_price is None or listing.current_price >= listing.reserve_price,
            'times_extended': listing.times_extended,
            'recent_bids': [
                {
                    'amount': str(b.amount),
                    'bidder': b.bidder.username,
                    'time': b.created.isoformat(),
                }
                for b in bids
            ]
        }

    # Handlers for group messages
    async def bid_placed(self, event):
        """Send bid update to client"""
        await self.send(text_data=json.dumps({
            'type': 'new_bid',
            'data': event['bid']
        }))

    async def auction_extended(self, event):
        """Send auction extension notice"""
        await self.send(text_data=json.dumps({
            'type': 'auction_extended',
            'data': event['data']
        }))

    async def auction_ended(self, event):
        """Send auction ended notice"""
        await self.send(text_data=json.dumps({
            'type': 'auction_ended',
            'data': event['data']
        }))
```

### WebSocket Routing

```python
# marketplace/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/auction/(?P<listing_id>\d+)/$', consumers.AuctionConsumer.as_asgi()),
]

# app/routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import marketplace.routing

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(
            marketplace.routing.websocket_urlpatterns
        )
    ),
})
```

### Live Bidding Room Template

```html
<!-- templates/marketplace/live_bidding_room.html -->
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="row">
        <!-- Main auction area -->
        <div class="col-lg-8">
            <div class="card mb-4">
                <div class="row g-0">
                    <div class="col-md-6">
                        <img src="{{ listing.image1.url }}" class="img-fluid rounded-start" alt="{{ listing.title }}">
                    </div>
                    <div class="col-md-6">
                        <div class="card-body">
                            <h4 class="card-title">{{ listing.title }}</h4>

                            <!-- Current bid display -->
                            <div class="mb-4">
                                <small class="text-muted text-uppercase">Current Bid</small>
                                <h2 class="mb-0" id="current-price">${{ listing.current_price }}</h2>
                                <small class="text-muted"><span id="bid-count">{{ listing.bids.count }}</span> bids</small>
                            </div>

                            <!-- Time remaining -->
                            <div class="mb-4">
                                <small class="text-muted text-uppercase">Time Remaining</small>
                                <h3 id="countdown" class="mb-0">--:--:--</h3>
                                {% if listing.times_extended > 0 %}
                                <small class="text-muted">Extended {{ listing.times_extended }} time{{ listing.times_extended|pluralize }}</small>
                                {% endif %}
                            </div>

                            <!-- Reserve indicator -->
                            <div class="mb-3" id="reserve-indicator">
                                {% if listing.reserve_price %}
                                    {% if listing.current_price >= listing.reserve_price %}
                                    <span class="badge bg-success">Reserve Met</span>
                                    {% else %}
                                    <span class="badge bg-warning text-dark">Reserve Not Met</span>
                                    {% endif %}
                                {% else %}
                                <span class="badge bg-dark">No Reserve</span>
                                {% endif %}
                            </div>

                            <!-- Bid form -->
                            {% if user.is_authenticated and user != listing.seller %}
                            <div class="bid-form">
                                <div class="input-group mb-2">
                                    <span class="input-group-text">$</span>
                                    <input type="number" id="bid-amount" class="form-control"
                                           min="{{ listing.minimum_next_bid }}"
                                           step="1"
                                           placeholder="Enter bid">
                                    <button class="btn btn-dark" id="place-bid-btn">Place Bid</button>
                                </div>
                                <small class="text-muted">Minimum bid: $<span id="min-bid">{{ listing.minimum_next_bid }}</span></small>

                                <!-- Quick bid buttons -->
                                <div class="d-flex gap-2 mt-2">
                                    <button class="btn btn-outline-dark btn-sm quick-bid" data-increment="1">+$1</button>
                                    <button class="btn btn-outline-dark btn-sm quick-bid" data-increment="5">+$5</button>
                                    <button class="btn btn-outline-dark btn-sm quick-bid" data-increment="10">+$10</button>
                                    <button class="btn btn-outline-dark btn-sm quick-bid" data-increment="25">+$25</button>
                                </div>

                                <!-- Max bid option -->
                                <div class="mt-3">
                                    <a href="#" data-bs-toggle="collapse" data-bs-target="#max-bid-form">
                                        Set Maximum Bid
                                    </a>
                                    <div class="collapse mt-2" id="max-bid-form">
                                        <div class="input-group">
                                            <span class="input-group-text">$</span>
                                            <input type="number" id="max-bid-amount" class="form-control" placeholder="Max bid">
                                            <button class="btn btn-outline-dark" id="set-max-bid-btn">Set</button>
                                        </div>
                                        <small class="text-muted">We'll bid for you up to this amount</small>
                                    </div>
                                </div>
                            </div>
                            {% elif not user.is_authenticated %}
                            <a href="{% url 'account_login' %}?next={{ request.path }}" class="btn btn-dark btn-lg w-100">
                                Log in to Bid
                            </a>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Bid history sidebar -->
        <div class="col-lg-4">
            <div class="card">
                <div class="card-header">
                    <h6 class="mb-0">Bid History</h6>
                </div>
                <div class="card-body p-0">
                    <ul class="list-group list-group-flush" id="bid-history">
                        {% for bid in listing.bids.all|slice:":15" %}
                        <li class="list-group-item d-flex justify-content-between">
                            <div>
                                <strong>{{ bid.bidder.username }}</strong>
                                <br>
                                <small class="text-muted">{{ bid.created|timesince }} ago</small>
                            </div>
                            <div class="text-end">
                                <strong>${{ bid.amount }}</strong>
                                {% if bid.triggered_extension %}
                                <br><small class="text-warning">Extended</small>
                                {% endif %}
                            </div>
                        </li>
                        {% empty %}
                        <li class="list-group-item text-center text-muted py-4">
                            No bids yet. Be the first!
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
const listingId = {{ listing.id }};
const endTime = new Date('{{ listing.auction_end.isoformat }}');
let socket = null;

// Connect WebSocket
function connectWebSocket() {
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/auction/${listingId}/`);

    socket.onopen = function(e) {
        console.log('Connected to auction');
    };

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        handleMessage(data);
    };

    socket.onclose = function(e) {
        console.log('Disconnected. Reconnecting...');
        setTimeout(connectWebSocket, 3000);
    };
}

function handleMessage(data) {
    switch(data.type) {
        case 'auction_state':
            updateAuctionState(data.data);
            break;
        case 'new_bid':
            handleNewBid(data.data);
            break;
        case 'auction_extended':
            handleExtension(data.data);
            break;
        case 'auction_ended':
            handleAuctionEnd(data.data);
            break;
        case 'error':
            showError(data.message);
            break;
    }
}

function handleNewBid(bid) {
    // Update price
    document.getElementById('current-price').textContent = '$' + bid.amount;
    document.getElementById('bid-count').textContent = parseInt(document.getElementById('bid-count').textContent) + 1;

    // Update minimum bid
    const minBid = parseFloat(bid.amount) + 1;
    document.getElementById('min-bid').textContent = minBid.toFixed(2);
    document.getElementById('bid-amount').min = minBid;
    document.getElementById('bid-amount').placeholder = minBid.toFixed(2);

    // Add to history
    const historyHtml = `
        <li class="list-group-item d-flex justify-content-between" style="animation: highlight 2s;">
            <div>
                <strong>${bid.bidder}</strong>
                <br>
                <small class="text-muted">Just now</small>
            </div>
            <div class="text-end">
                <strong>$${bid.amount}</strong>
                ${bid.extended ? '<br><small class="text-warning">Extended</small>' : ''}
            </div>
        </li>
    `;
    document.getElementById('bid-history').insertAdjacentHTML('afterbegin', historyHtml);

    // Update reserve indicator
    if (bid.reserve_met) {
        document.getElementById('reserve-indicator').innerHTML = '<span class="badge bg-success">Reserve Met</span>';
    }

    // Handle extension
    if (bid.extended && bid.new_end_time) {
        endTime = new Date(bid.new_end_time);
        showNotification('Auction extended by 15 minutes!');
    }
}

function placeBid() {
    const amount = document.getElementById('bid-amount').value;
    if (!amount) return;

    socket.send(JSON.stringify({
        type: 'place_bid',
        amount: amount
    }));
}

// Quick bid buttons
document.querySelectorAll('.quick-bid').forEach(btn => {
    btn.addEventListener('click', function() {
        const currentMin = parseFloat(document.getElementById('min-bid').textContent);
        const increment = parseInt(this.dataset.increment);
        document.getElementById('bid-amount').value = (currentMin + increment - 1).toFixed(2);
        placeBid();
    });
});

// Countdown timer
function updateCountdown() {
    const now = new Date();
    const diff = endTime - now;

    if (diff <= 0) {
        document.getElementById('countdown').textContent = 'ENDED';
        document.getElementById('countdown').classList.add('text-danger');
        return;
    }

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    document.getElementById('countdown').textContent =
        `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

    // Highlight when ending soon
    if (diff < 60000) {
        document.getElementById('countdown').classList.add('text-danger', 'fw-bold');
    } else if (diff < 300000) {
        document.getElementById('countdown').classList.add('text-warning');
    }
}

// Initialize
connectWebSocket();
setInterval(updateCountdown, 1000);
updateCountdown();

document.getElementById('place-bid-btn').addEventListener('click', placeBid);
</script>

<style>
@keyframes highlight {
    0% { background-color: #ffc107; }
    100% { background-color: transparent; }
}
</style>
{% endblock %}
```

---

## 6. Phase 5: Auction Events

### Views

```python
# marketplace/views/auction_events.py

class AuctionEventListView(ListView):
    """List all auction events"""
    model = AuctionEvent
    template_name = 'marketplace/auction_events.html'
    context_object_name = 'events'

    def get_queryset(self):
        now = timezone.now()
        return AuctionEvent.objects.filter(
            is_published=True
        ).annotate(
            status=Case(
                When(bidding_end__lt=now, then=Value('ended')),
                When(bidding_start__gt=now, then=Value('upcoming')),
                default=Value('live'),
                output_field=CharField(),
            )
        ).order_by('-bidding_start')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        context['live_events'] = self.object_list.filter(
            bidding_start__lte=now,
            bidding_end__gt=now
        )
        context['upcoming_events'] = self.object_list.filter(
            bidding_start__gt=now
        )[:5]
        context['past_events'] = self.object_list.filter(
            bidding_end__lt=now
        )[:10]

        return context


class AuctionEventDetailView(DetailView):
    """Single auction event with its lots"""
    model = AuctionEvent
    template_name = 'marketplace/auction_event_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        listings = self.object.listings.filter(status='active').order_by('lot_number')

        # Filtering
        category = self.request.GET.get('category')
        if category:
            listings = listings.filter(category__slug=category)

        sort = self.request.GET.get('sort', 'lot')
        if sort == 'price_low':
            listings = listings.order_by('current_price')
        elif sort == 'price_high':
            listings = listings.order_by('-current_price')
        elif sort == 'bids':
            listings = listings.annotate(bid_count=Count('bids')).order_by('-bid_count')
        elif sort == 'ending':
            listings = listings.order_by('auction_end')

        context['listings'] = listings
        context['categories'] = Category.objects.filter(
            listings__auction_event=self.object
        ).distinct()

        # Event status
        now = timezone.now()
        if now < self.object.bidding_start:
            context['event_status'] = 'upcoming'
        elif now > self.object.bidding_end:
            context['event_status'] = 'ended'
        else:
            context['event_status'] = 'live'

        return context
```

### Admin for Creating Events

```python
# marketplace/admin.py

@admin.register(AuctionEvent)
class AuctionEventAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'bidding_start', 'bidding_end', 'total_lots', 'is_published']
    list_filter = ['event_type', 'is_published']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'event_type', 'description')
        }),
        ('Timing', {
            'fields': ('preview_start', 'bidding_start', 'bidding_end')
        }),
        ('Display', {
            'fields': ('cover_image', 'is_featured', 'is_published')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class AddToEventAction(admin.ModelAdmin):
    """Add action to add listings to events"""
    actions = ['add_to_weekly_event']

    @admin.action(description='Add to current weekly auction')
    def add_to_weekly_event(self, request, queryset):
        # Get or create current weekly event
        event = AuctionEvent.objects.filter(
            event_type='weekly',
            bidding_end__gt=timezone.now()
        ).first()

        if not event:
            self.message_user(request, "No active weekly auction found", level='error')
            return

        lot_number = event.listings.count() + 1
        for listing in queryset:
            listing.auction_event = event
            listing.lot_number = lot_number
            listing.save()
            lot_number += 1

        event.total_lots = event.listings.count()
        event.save()

        self.message_user(request, f"Added {queryset.count()} listings to {event.name}")
```

---

## 7. Phase 6: Offer/Counteroffer System

### Views

```python
# marketplace/views/offers.py

@login_required
def make_offer(request, listing_id):
    """Make an offer on a listing"""
    listing = get_object_or_404(Listing, id=listing_id, allow_offers=True, status='active')

    if listing.seller == request.user:
        messages.error(request, "You can't make an offer on your own listing")
        return redirect(listing.get_absolute_url())

    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        message = request.POST.get('message', '')[:500]

        # Validate minimum offer
        min_offer = listing.price * Decimal(listing.minimum_offer_percent / 100)
        if amount < min_offer:
            messages.error(request, f"Minimum offer is ${min_offer:.2f}")
            return redirect(listing.get_absolute_url())

        # Check for existing pending offer
        existing = Offer.objects.filter(
            listing=listing,
            buyer=request.user,
            status='pending'
        ).first()

        if existing:
            messages.error(request, "You already have a pending offer on this item")
            return redirect(listing.get_absolute_url())

        offer = Offer.objects.create(
            listing=listing,
            buyer=request.user,
            amount=amount,
            message=message,
            expires_at=timezone.now() + timedelta(days=2),
        )

        # Notify seller
        from alerts.tasks import send_offer_notification
        send_offer_notification.delay(offer.id)

        messages.success(request, "Your offer has been sent!")
        return redirect('marketplace:my_offers')

    return render(request, 'marketplace/make_offer.html', {'listing': listing})


@login_required
def respond_to_offer(request, offer_id):
    """Seller responds to an offer"""
    offer = get_object_or_404(
        Offer,
        id=offer_id,
        listing__seller=request.user,
        status='pending'
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'accept':
            offer.status = 'accepted'
            offer.responded_at = timezone.now()
            offer.save()

            # Create order at offer price
            from .services import create_order_from_offer
            order = create_order_from_offer(offer)

            messages.success(request, "Offer accepted! Order created.")
            return redirect(order.get_absolute_url())

        elif action == 'decline':
            offer.status = 'declined'
            offer.responded_at = timezone.now()
            offer.save()

            # Notify buyer
            from alerts.tasks import send_offer_declined_notification
            send_offer_declined_notification.delay(offer.id)

            messages.success(request, "Offer declined")
            return redirect('marketplace:seller_offers')

        elif action == 'counter':
            counter_amount = Decimal(request.POST.get('counter_amount', 0))
            counter_message = request.POST.get('counter_message', '')[:500]

            if counter_amount <= offer.amount:
                messages.error(request, "Counter offer must be higher than original offer")
                return redirect(request.path)

            offer.status = 'countered'
            offer.counter_amount = counter_amount
            offer.counter_message = counter_message
            offer.countered_at = timezone.now()
            offer.expires_at = timezone.now() + timedelta(days=2)
            offer.save()

            # Notify buyer
            from alerts.tasks import send_counter_offer_notification
            send_counter_offer_notification.delay(offer.id)

            messages.success(request, f"Counter offer of ${counter_amount} sent")
            return redirect('marketplace:seller_offers')

    return render(request, 'marketplace/respond_to_offer.html', {'offer': offer})


@login_required
def accept_counter_offer(request, offer_id):
    """Buyer accepts a counter offer"""
    offer = get_object_or_404(
        Offer,
        id=offer_id,
        buyer=request.user,
        status='countered'
    )

    if request.method == 'POST':
        offer.status = 'accepted'
        offer.responded_at = timezone.now()
        offer.save()

        # Create order at counter price
        from .services import create_order_from_offer
        order = create_order_from_offer(offer, use_counter_price=True)

        messages.success(request, "Counter offer accepted!")
        return redirect(order.get_absolute_url())

    return redirect('marketplace:my_offers')
```

---

## 8. Phase 7: Seller Tools

### Bulk Import

```python
# seller_tools/views.py

@login_required
def bulk_import_view(request):
    """Upload CSV for bulk listing creation"""
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.error(request, "Please select a file")
            return redirect(request.path)

        # Validate file type
        if not file.name.endswith(('.csv', '.xlsx')):
            messages.error(request, "Please upload a CSV or Excel file")
            return redirect(request.path)

        bulk_import = BulkImport.objects.create(
            user=request.user,
            file=file,
            file_type=file.name.split('.')[-1],
        )

        # Process asynchronously
        from .tasks import process_bulk_import
        process_bulk_import.delay(bulk_import.id)

        messages.success(request, "File uploaded! Processing...")
        return redirect('seller_tools:bulk_import_status', pk=bulk_import.pk)

    return render(request, 'seller_tools/bulk_import.html')


@login_required
def bulk_import_status(request, pk):
    """Check status of bulk import"""
    bulk_import = get_object_or_404(BulkImport, pk=pk, user=request.user)

    return render(request, 'seller_tools/bulk_import_status.html', {
        'import': bulk_import,
        'rows': bulk_import.rows.all()[:100],
    })
```

### Bulk Import Task

```python
# seller_tools/tasks.py

import csv
from celery import shared_task

@shared_task
def process_bulk_import(import_id):
    """Process a bulk import file"""
    bulk_import = BulkImport.objects.get(id=import_id)
    bulk_import.status = 'processing'
    bulk_import.started_at = timezone.now()
    bulk_import.save()

    try:
        file_path = bulk_import.file.path

        if bulk_import.file_type == 'csv':
            rows = list(csv.DictReader(open(file_path, 'r')))
        else:
            import openpyxl
            wb = openpyxl.load_workbook(file_path)
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
            rows = [dict(zip(headers, [cell.value for cell in row])) for row in ws.iter_rows(min_row=2)]

        bulk_import.total_rows = len(rows)
        bulk_import.save()

        for i, row_data in enumerate(rows, 1):
            try:
                # Create listing from row
                listing = create_listing_from_row(bulk_import.user, row_data)

                BulkImportRow.objects.create(
                    bulk_import=bulk_import,
                    row_number=i,
                    data=row_data,
                    status='success',
                    listing=listing,
                )
                bulk_import.success_count += 1

            except Exception as e:
                BulkImportRow.objects.create(
                    bulk_import=bulk_import,
                    row_number=i,
                    data=row_data,
                    status='error',
                    error_message=str(e),
                )
                bulk_import.error_count += 1
                bulk_import.errors.append({'row': i, 'error': str(e)})

            bulk_import.processed_rows = i
            bulk_import.save()

        bulk_import.status = 'completed' if bulk_import.error_count == 0 else 'partial'
        bulk_import.completed_at = timezone.now()
        bulk_import.save()

    except Exception as e:
        bulk_import.status = 'failed'
        bulk_import.errors.append({'error': str(e)})
        bulk_import.save()


def create_listing_from_row(user, row):
    """Create a listing from CSV row data"""
    # Map CSV columns to model fields
    title = row.get('title') or row.get('Title') or row.get('name')
    price = Decimal(str(row.get('price') or row.get('Price') or 0))
    description = row.get('description') or row.get('Description') or ''
    category_name = row.get('category') or row.get('Category')
    condition = row.get('condition') or row.get('Condition') or 'good'

    if not title or not price:
        raise ValueError("Title and price are required")

    # Find category
    category = Category.objects.filter(name__iexact=category_name).first()
    if not category:
        raise ValueError(f"Category '{category_name}' not found")

    # Create listing
    listing = Listing.objects.create(
        seller=user,
        title=title,
        description=description,
        price=price,
        category=category,
        condition=condition.lower().replace(' ', '_'),
        status='draft',  # Start as draft for review
    )

    return listing
```

### Seller Subscription

```python
# seller_tools/views.py

@login_required
def subscription_view(request):
    """Manage seller subscription"""
    subscription, created = SellerSubscription.objects.get_or_create(
        user=request.user,
        defaults={'tier': 'starter'}
    )

    tier_info = {
        'starter': {'price': 0, 'max_listings': 50, 'commission': 12.95, 'featured': 0},
        'basic': {'price': 9.99, 'max_listings': 250, 'commission': 11.95, 'featured': 5},
        'featured': {'price': 24.99, 'max_listings': 1000, 'commission': 9.95, 'featured': 15},
        'premium': {'price': 49.99, 'max_listings': 999999, 'commission': 7.95, 'featured': 999999},
    }

    return render(request, 'seller_tools/subscription.html', {
        'subscription': subscription,
        'tier_info': tier_info,
        'current_listing_count': Listing.objects.filter(seller=request.user, status='active').count(),
    })
```

---

## 9. Phase 8: Enhanced Search & Notifications

### Advanced Search

```python
# items/views.py

class AdvancedSearchView(ListView):
    """Advanced search with all filters"""
    model = Listing
    template_name = 'items/advanced_search.html'
    paginate_by = 48

    def get_queryset(self):
        qs = Listing.objects.filter(status='active')

        # Text search
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q)
            )

        # Category
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category__slug=category)

        # Price range
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)

        # Condition
        condition = self.request.GET.get('condition')
        if condition:
            qs = qs.filter(condition=condition)

        # Grading company
        grading_company = self.request.GET.get('grading_company')
        if grading_company:
            if grading_company == 'raw':
                qs = qs.filter(is_graded=False)
            else:
                qs = qs.filter(grading_company=grading_company)

        # Grade range
        min_grade = self.request.GET.get('min_grade')
        max_grade = self.request.GET.get('max_grade')
        if min_grade:
            qs = qs.filter(grade__gte=min_grade)
        if max_grade:
            qs = qs.filter(grade__lte=max_grade)

        # Year range
        min_year = self.request.GET.get('min_year')
        max_year = self.request.GET.get('max_year')
        if min_year:
            qs = qs.filter(price_guide_item__year__gte=min_year)
        if max_year:
            qs = qs.filter(price_guide_item__year__lte=max_year)

        # Listing type
        listing_type = self.request.GET.get('type')
        if listing_type == 'auction':
            qs = qs.filter(listing_type='auction')
        elif listing_type == 'fixed':
            qs = qs.filter(listing_type='fixed')

        # Ending soon (for auctions)
        ending = self.request.GET.get('ending')
        if ending:
            hours = int(ending)
            qs = qs.filter(
                listing_type='auction',
                auction_end__lte=timezone.now() + timedelta(hours=hours)
            )

        # Free shipping
        if self.request.GET.get('free_shipping'):
            qs = qs.filter(Q(shipping_price=0) | Q(shipping_price__isnull=True))

        # No reserve
        if self.request.GET.get('no_reserve'):
            qs = qs.filter(no_reserve=True)

        # Seller rating
        min_rating = self.request.GET.get('min_seller_rating')
        if min_rating:
            qs = qs.filter(seller__profile__rating__gte=min_rating)

        # Sort
        sort = self.request.GET.get('sort', 'newest')
        if sort == 'newest':
            qs = qs.order_by('-created')
        elif sort == 'price_low':
            qs = qs.order_by('price')
        elif sort == 'price_high':
            qs = qs.order_by('-price')
        elif sort == 'ending':
            qs = qs.filter(listing_type='auction').order_by('auction_end')
        elif sort == 'popular':
            qs = qs.annotate(view_count=Count('viewed_by')).order_by('-view_count')

        return qs
```

### Notification System

```python
# alerts/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

@shared_task
def send_outbid_notification(user_id, listing_id, new_amount):
    """Notify user they've been outbid"""
    from accounts.models import User
    from marketplace.models import Listing

    user = User.objects.get(id=user_id)
    listing = Listing.objects.get(id=listing_id)

    # Create alert record
    Alert.objects.create(
        user=user,
        alert_type='outbid',
        title='You\'ve been outbid!',
        message=f'Someone bid ${new_amount} on "{listing.title}"',
        link=listing.get_absolute_url(),
    )

    # Send email if enabled
    if user.profile.email_notifications:
        html_message = render_to_string('emails/outbid.html', {
            'user': user,
            'listing': listing,
            'new_amount': new_amount,
        })

        send_mail(
            subject=f'You\'ve been outbid on {listing.title}',
            message='',
            html_message=html_message,
            from_email='HeroesAndMore <noreply@mail.heroesandmore.com>',
            recipient_list=[user.email],
        )


@shared_task
def check_saved_search_matches():
    """Check all saved searches for new matches"""
    for saved_search in SavedSearch.objects.filter(is_active=True):
        check_single_saved_search.delay(saved_search.id)


@shared_task
def check_single_saved_search(search_id):
    """Check a single saved search for new matches"""
    saved_search = SavedSearch.objects.get(id=search_id)

    # Build query from saved filters
    qs = Listing.objects.filter(status='active')

    if saved_search.query:
        qs = qs.filter(title__icontains=saved_search.query)
    if saved_search.category:
        qs = qs.filter(category=saved_search.category)
    if saved_search.min_price:
        qs = qs.filter(price__gte=saved_search.min_price)
    if saved_search.max_price:
        qs = qs.filter(price__lte=saved_search.max_price)
    # ... more filters

    # Only new listings since last check
    if saved_search.last_notified:
        qs = qs.filter(created__gt=saved_search.last_notified)

    matches = list(qs[:10])

    if matches:
        saved_search.matches_count = len(matches)
        saved_search.last_notified = timezone.now()
        saved_search.save()

        # Send notification
        if saved_search.notify_email:
            send_saved_search_matches.delay(search_id, [m.id for m in matches])


@shared_task
def check_price_alerts():
    """Check price alerts for matches"""
    for alert in PriceAlert.objects.filter(is_active=True, is_triggered=False):
        # Find listings at or below target price
        listings = Listing.objects.filter(
            status='active',
            price_guide_item=alert.price_guide_item,
            price__lte=alert.target_price,
        )

        if alert.grade:
            listings = listings.filter(grade=alert.grade)

        listing = listings.first()

        if listing:
            alert.is_triggered = True
            alert.triggered_at = timezone.now()
            alert.triggered_listing = listing
            alert.save()

            # Notify user
            send_price_alert_notification.delay(alert.id)
```

---

## 10. Phase 9: Trust & Safety

### Verified Seller Program

```python
# accounts/views.py

@login_required
def seller_verification_view(request):
    """Apply for verified seller status"""
    profile = request.user.profile

    # Check eligibility
    eligible = (
        profile.total_sales_count >= 10 and
        profile.rating >= 4.5 and
        profile.rating_count >= 5
    )

    if request.method == 'POST' and eligible:
        # Start verification process
        profile.verification_requested = True
        profile.save()
        messages.success(request, "Verification request submitted!")
        return redirect('accounts:settings')

    return render(request, 'accounts/seller_verification.html', {
        'profile': profile,
        'eligible': eligible,
        'requirements': {
            'sales': {'required': 10, 'current': profile.total_sales_count},
            'rating': {'required': 4.5, 'current': profile.rating},
            'reviews': {'required': 5, 'current': profile.rating_count},
        }
    })
```

### Report System

```python
# marketplace/models.py

class Report(models.Model):
    """Report a listing or user"""
    REPORT_TYPES = [
        ('counterfeit', 'Counterfeit/Fake Item'),
        ('misrepresented', 'Item Misrepresented'),
        ('stolen', 'Suspected Stolen Item'),
        ('inappropriate', 'Inappropriate Content'),
        ('scam', 'Suspected Scam'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    listing = models.ForeignKey(Listing, null=True, blank=True, on_delete=models.CASCADE)
    reported_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='reports_received')

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    description = models.TextField()
    evidence_images = models.JSONField(default=list)  # URLs to uploaded images

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports_resolved')
    resolved_at = models.DateTimeField(null=True)

    created = models.DateTimeField(auto_now_add=True)
```

---

## 11. Infrastructure Requirements

### ASGI Configuration for Channels

```python
# app/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

django_asgi_app = get_asgi_application()

from marketplace.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
```

### Settings Updates

```python
# app/settings.py

INSTALLED_APPS = [
    # ... existing apps
    'channels',
    'pricing',
    'scanner',
    'seller_tools',
]

# Channels
ASGI_APPLICATION = 'app.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_URL)],
        },
    },
}

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'update-collection-values': {
        'task': 'collections.tasks.update_collection_values',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2am
    },
    'check-saved-searches': {
        'task': 'alerts.tasks.check_saved_search_matches',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'check-price-alerts': {
        'task': 'alerts.tasks.check_price_alerts',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'update-price-guide-stats': {
        'task': 'pricing.tasks.update_all_price_guide_stats',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3am
    },
}

# Google Cloud Vision (for image recognition)
GOOGLE_CLOUD_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
```

### Requirements

```
# requirements.txt additions
channels==4.0.0
channels-redis==4.1.0
google-cloud-vision==3.4.0
openpyxl==3.1.2
```

---

## 12. File Structure

```
heroesandmore/
├── pricing/                    # NEW APP
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   ├── serializers.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── price_calculator.py
│   │   └── data_import.py
│   ├── tasks.py
│   └── templates/pricing/
│       ├── price_guide_list.html
│       ├── price_guide_detail.html
│       └── components/
│           └── price_chart.html
│
├── scanner/                    # NEW APP
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── recognition.py
│   ├── tasks.py
│   └── templates/scanner/
│       ├── scan_item.html
│       ├── scan_result.html
│       └── create_listing.html
│
├── seller_tools/               # NEW APP
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   ├── tasks.py
│   └── templates/seller_tools/
│       ├── bulk_import.html
│       ├── bulk_import_status.html
│       └── subscription.html
│
├── marketplace/
│   ├── consumers.py            # NEW - WebSocket consumers
│   ├── routing.py              # NEW - WebSocket routing
│   ├── models.py               # UPDATED - AuctionEvent, Offer, etc.
│   ├── views/
│   │   ├── __init__.py
│   │   ├── listings.py
│   │   ├── auction_events.py   # NEW
│   │   ├── offers.py           # NEW
│   │   └── live_bidding.py     # NEW
│   └── templates/marketplace/
│       ├── auction_events.html         # NEW
│       ├── auction_event_detail.html   # NEW
│       ├── live_bidding_room.html      # NEW
│       ├── make_offer.html             # NEW
│       └── respond_to_offer.html       # NEW
│
├── collections/
│   ├── models.py               # UPDATED - CollectionValueSnapshot
│   ├── views.py                # UPDATED - Portfolio views
│   ├── tasks.py                # NEW - Value update tasks
│   └── templates/collections/
│       └── portfolio.html      # NEW
│
├── alerts/
│   ├── models.py               # UPDATED - SavedSearch, PriceAlert
│   ├── views.py                # UPDATED
│   └── tasks.py                # UPDATED - Notification tasks
│
├── items/
│   └── views.py                # UPDATED - Advanced search
│
├── accounts/
│   ├── models.py               # UPDATED - RecentlyViewed, verification
│   └── views.py                # UPDATED - Verification views
│
├── app/
│   ├── asgi.py                 # UPDATED - Channels
│   ├── settings.py             # UPDATED - New apps, Celery beat
│   └── urls.py                 # UPDATED - New URL patterns
│
└── templates/
    ├── components/
    │   ├── price_chart.html    # NEW - Reusable chart component
    │   └── bid_history.html    # NEW
    └── emails/
        ├── outbid.html         # NEW
        ├── offer_received.html # NEW
        └── price_alert.html    # NEW
```

---

## Implementation Checklist

### Week 1-2: Foundation
- [ ] Create `pricing` app with models
- [ ] Create `scanner` app with models
- [ ] Create `seller_tools` app with models
- [ ] Update existing models (Listing, Collection, etc.)
- [ ] Run migrations
- [ ] Set up Django Channels

### Week 3-4: Price Guide
- [ ] Price guide views and templates
- [ ] Price suggestion API endpoint
- [ ] Price history charts (Chart.js)
- [ ] Celery tasks for stats updates
- [ ] Admin interface for price guide

### Week 5-6: Scanner
- [ ] Google Cloud Vision integration
- [ ] Image recognition service
- [ ] Scan views and templates
- [ ] Create listing from scan flow
- [ ] Add to collection from scan flow

### Week 7-8: Live Bidding
- [ ] WebSocket consumers
- [ ] Live bidding room template
- [ ] Extended bidding logic
- [ ] Real-time bid updates
- [ ] Auto-bid system

### Week 9-10: Auction Events & Offers
- [ ] Auction event models and admin
- [ ] Event listing pages
- [ ] Weekly auction automation
- [ ] Offer/counteroffer system
- [ ] Offer notifications

### Week 11-12: Seller Tools & Notifications
- [ ] Bulk import with CSV
- [ ] Seller subscription tiers
- [ ] Enhanced search filters
- [ ] Saved search alerts
- [ ] Price drop alerts
- [ ] Email notification templates

### Week 13: Trust & Safety
- [ ] Verified seller program
- [ ] Report system
- [ ] Admin moderation tools

### Week 14: Polish & Deploy
- [ ] Testing all features
- [ ] Performance optimization
- [ ] Documentation
- [ ] Production deployment

---

## Success Metrics

After implementation, track:
- **User engagement**: Time on site, pages per session
- **Auction participation**: Bids per auction, bid frequency
- **Seller adoption**: Bulk imports, subscription upgrades
- **Price guide usage**: Searches, listing pre-fills
- **Scanner usage**: Scans per day, conversion to listings
- **Notification effectiveness**: Open rates, click-through rates

This plan will bring HeroesAndMore to feature parity with HipComic and position it as a serious competitor in the collectibles marketplace space.
